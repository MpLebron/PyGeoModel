"""Main user-facing PyGeoModel entry point."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .client import OpenGMSClient
from .config import get_llm_config
from .context import NotebookContext
from .models import ModelService, ModelSummary
from .results import QAResult, RecommendationResult, TaskResult


class GeoModeler:
    """Access OpenGMS model services from Python and notebooks."""

    def __init__(
        self,
        data_path: str | Path | None = None,
        client: OpenGMSClient | None = None,
    ):
        self.data_path = self._resolve_data_path(data_path)
        self._models_data = self._load_catalog()
        self.model_names = list(self._models_data.keys())
        self.client = client or OpenGMSClient()
        self.last_result: TaskResult | None = None
        self.last_recommendation: RecommendationResult | None = None
        self.last_answer: QAResult | None = None
        self._notebook_interface = None

    def search_models(self, query: str = "", limit: int = 20) -> list[ModelSummary]:
        query = (query or "").strip().lower()
        scored: list[tuple[int, ModelSummary]] = []
        for name, raw in self._models_data.items():
            service = ModelService.from_raw(name, raw)
            haystack = " ".join(
                [
                    name,
                    service.description,
                    service.author,
                    " ".join(service.tags),
                    " ".join(service.tags_en),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            score = 0
            if query:
                if query in name.lower():
                    score += 20
                if query in service.description.lower():
                    score += 10
                if any(query in tag.lower() for tag in service.tags + service.tags_en):
                    score += 5
            scored.append((score, service.summary()))
        scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
        return [summary for _, summary in scored[:limit]]

    def get_model(self, model_name: str) -> ModelService:
        if model_name not in self._models_data:
            raise KeyError(f"Model '{model_name}' was not found in the local OpenGMS catalog")
        return ModelService.from_raw(model_name, self._models_data[model_name])

    def invoke(
        self,
        model_name: str,
        params: dict[str, Any],
        wait: bool = True,
        output_dir: str | Path | None = None,
        record_path: str | Path | None = None,
    ) -> TaskResult:
        model = self.get_model(model_name)
        normalized_params = model.normalize_params(params)
        started = time.time()
        response = self.client.create_task(model_name, normalized_params, wait=wait)
        result = TaskResult(
            model_name=model.name,
            model_id=model.model_id,
            model_md5=model.md5,
            params=params,
            uploaded_inputs=normalized_params,
            task_id=response.get("task_id"),
            status=response.get("status", "completed" if wait else "submitted"),
            outputs=response.get("outputs", []),
            execution_time=response.get("execution_time", time.time() - started),
            endpoint=getattr(self.client, "manager_url", None),
        )
        if output_dir:
            result.download(output_dir)
        if record_path:
            result.to_json(record_path)
        self.last_result = result
        return result

    def suggest_model(
        self,
        context: str | None = None,
        data_context: str | None = None,
        include_trace: bool = True,
        return_result: bool = True,
    ) -> RecommendationResult | None:
        ctx = self._recommendation_context(context, data_context)
        raw_response: dict[str, Any] = {}
        final_outputs: dict[str, Any] = {}
        cfg = get_llm_config()
        if cfg.dify_api_key:
            payload = {
                "inputs": {
                    "modeling_history": ctx["modeling_history"],
                    "data_context": ctx["data_context"],
                },
                "response_mode": "blocking",
                "user": "jupyter_user",
            }
            response = requests.post(
                f"{cfg.dify_base_url.rstrip('/')}/workflows/run",
                headers={"Authorization": f"Bearer {cfg.dify_api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            raw_response = response.json()
            final_outputs = raw_response.get("data", {}).get("outputs", {})
            if "text" in final_outputs and isinstance(final_outputs["text"], str):
                try:
                    final_outputs = json.loads(final_outputs["text"])
                except json.JSONDecodeError:
                    pass
        else:
            final_outputs = self._local_recommendation_fallback(ctx)
            raw_response = {"source": "local_fallback", "outputs": final_outputs}

        primary = final_outputs.get("model_recommendation") or final_outputs.get("recommended_model") or {}
        recommended_data = final_outputs.get("recommended_data", {})
        trace = {
            "available": bool(include_trace),
            "note": "Full node-level trace requires Dify workflow end-node trace outputs.",
        }
        if include_trace:
            trace.update({key: final_outputs.get(key) for key in final_outputs if key not in {"model_recommendation", "recommended_data"}})
        recommendation = RecommendationResult(
            primary_model=primary,
            candidates=final_outputs.get("candidates", []),
            recommended_data=recommended_data,
            context=ctx,
            trace=trace,
            raw_response=raw_response,
        )
        self.last_recommendation = recommendation
        if return_result:
            return recommendation
        self._display_recommendation(recommendation)
        return None

    def ask_model(self, model_name: str, question: str, context: str | None = None) -> QAResult:
        model = self.get_model(model_name)
        rewritten = question.strip()
        metadata_answer = self._metadata_answer(model, question)
        sources = [{"type": "OpenGMS metadata", "model": model.name}]
        raw_response: dict[str, Any] = {"source": "metadata_fallback"}
        cfg = get_llm_config()
        if cfg.openai_api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_base_url)
                completion = client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You answer questions about an OpenGMS model service using the provided metadata. "
                                "Be concise and identify uncertainty."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "question": question,
                                    "model": model.to_dict(),
                                    "context": context or "",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    temperature=0.2,
                )
                metadata_answer = completion.choices[0].message.content or metadata_answer
                raw_response = {"source": "openai", "model": "gpt-4.1-nano"}
            except Exception as exc:
                raw_response = {"source": "metadata_fallback", "openai_error": str(exc)}
        result = QAResult(
            question=question,
            rewritten_question=rewritten,
            answer=metadata_answer,
            model_name=model.name,
            sources=sources,
            context={"user_context": context or ""},
            raw_response=raw_response,
        )
        self.last_answer = result
        return result

    def show_models(self):
        return self._interface().show_models()

    def invoke_model(self, model_name: str):
        return self._interface().invoke_model(model_name)

    def show_model(self, model_name: str):
        return self.invoke_model(model_name)

    def _interface(self):
        if self._notebook_interface is None:
            from .notebook import NotebookInterface

            self._notebook_interface = NotebookInterface(self)
        return self._notebook_interface

    def _recommendation_context(self, context: str | None, data_context: str | None) -> dict[str, str]:
        if context is not None or data_context is not None:
            return {
                "modeling_history": context or "",
                "data_context": data_context or "",
            }
        notebook_context = NotebookContext()
        return notebook_context.to_dict()

    def _local_recommendation_fallback(self, ctx: dict[str, str]) -> dict[str, Any]:
        query = f"{ctx.get('modeling_history', '')} {ctx.get('data_context', '')}".strip()
        summaries = self.search_models(query[:120] if query else "", limit=5)
        if not summaries:
            summaries = self.search_models("", limit=5)
        primary = summaries[0].to_dict() if summaries else {}
        return {
            "model_recommendation": {
                "name": primary.get("name", ""),
                "description": primary.get("description", ""),
                "key_strengths": [],
                "recommendation_reason": "Selected from the local OpenGMS model catalog using metadata matching.",
                "application_scenario": "",
            },
            "candidates": [item.to_dict() for item in summaries],
            "recommended_data": {"local_data": [], "knowledge_base_data": []},
        }

    def _metadata_answer(self, model: ModelService, question: str) -> str:
        inputs = ", ".join(item.name for item in model.inputs[:10]) or "no inputs listed"
        outputs = ", ".join(item.name for item in model.outputs[:10]) or "no outputs listed"
        return (
            f"{model.name} is described in the OpenGMS metadata as: {model.description}\n\n"
            f"Listed inputs include: {inputs}.\n"
            f"Listed outputs include: {outputs}."
        )

    def _display_recommendation(self, recommendation: RecommendationResult) -> None:
        try:
            from IPython.display import HTML, display

            model = recommendation.primary_model
            html = f"<h3>Model Recommendation</h3><b>{model.get('name', '')}</b><p>{model.get('recommendation_reason', '')}</p>"
            display(HTML(html))
        except Exception:
            print(recommendation.to_dict())

    def _load_catalog(self) -> dict[str, Any]:
        with self.data_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def _resolve_data_path(self, data_path: str | Path | None) -> Path:
        if data_path is not None:
            resolved = Path(data_path)
            if not resolved.exists():
                raise FileNotFoundError(str(resolved))
            return resolved
        candidates = [
            Path(__file__).resolve().parent / "data" / "computeModel.json",
            Path(__file__).resolve().parent.parent / "data" / "computeModel.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("Could not locate data/computeModel.json")
