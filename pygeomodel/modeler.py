"""Main user-facing PyGeoModel entry point."""

from __future__ import annotations

import csv
import json
import re
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
        self._uses_custom_data_path = data_path is not None
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
        scored: list[tuple[int, int, ModelSummary]] = []
        for name, raw in self._models_data.items():
            service = ModelService.from_raw(name, raw)
            haystack = " ".join(
                [
                    name,
                    service.display_name,
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
                if query in service.display_name.lower():
                    score += 25
                if query in name.lower():
                    score += 20
                if query in service.description.lower():
                    score += 10
                if any(query in tag.lower() for tag in service.tags + service.tags_en):
                    score += 5
            scored.append((score, service.registry_order, service.summary()))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2].display_name.lower(), item[2].name.lower()))
        return [summary for _, _, summary in scored[:limit]]

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
            record_path=str(record_path) if record_path else None,
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
        if not cfg.dify_api_key:
            raise RuntimeError("DIFY_API_KEY is required for context-aware model recommendation")

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
        response_payload = response.json()
        raw_response = {"source": "dify_workflow", "response": response_payload}
        final_outputs = self._parse_dify_outputs(response_payload.get("data", {}).get("outputs", {}))

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
            candidates=self._candidate_models_from_outputs(final_outputs, primary),
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

    def _parse_dify_outputs(self, outputs: Any) -> dict[str, Any]:
        if not isinstance(outputs, dict):
            return {}
        if self._has_recommendation_payload(outputs):
            return outputs

        for value in outputs.values():
            if isinstance(value, dict) and self._has_recommendation_payload(value):
                return value
            if isinstance(value, str):
                parsed = self._parse_json_payload(value)
                if isinstance(parsed, dict):
                    return parsed
        return outputs

    def _has_recommendation_payload(self, payload: dict[str, Any]) -> bool:
        return any(
            key in payload
            for key in ("model_recommendation", "recommended_model", "recommended_data", "candidate_models", "candidates")
        )

    def _candidate_models_from_outputs(
        self,
        outputs: dict[str, Any],
        primary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidates = outputs.get("candidate_models") or outputs.get("candidates") or []
        if not isinstance(candidates, list):
            return []

        primary_name = str(primary.get("name", "")).strip().lower()
        normalized: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            item = dict(candidate)
            item.setdefault("rank", index)
            candidate_name = str(item.get("name", "")).strip().lower()
            is_primary = bool(item.get("is_primary")) or bool(primary_name and candidate_name == primary_name)
            item["is_primary"] = is_primary
            normalized.append(item)

        return normalized

    def _parse_json_payload(self, text: str) -> Any:
        cleaned = text.strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            json_object = self._extract_first_json_object(cleaned)
            if not json_object:
                return None
            try:
                return json.loads(json_object)
            except json.JSONDecodeError:
                return None

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def ask_model(
        self,
        model_name: str,
        question: str,
        context: str | None = None,
    ) -> QAResult:
        model = self.get_model(model_name)
        rewritten = question.strip()
        answer = self._call_openai_qa(model, rewritten, context)
        sources = [{"type": "OpenGMS metadata", "model": model.name}]
        cfg = get_llm_config()
        raw_response: dict[str, Any] = {
            "source": "openai_web",
            "openai_model": cfg.openai_model,
        }
        result = QAResult(
            question=question,
            rewritten_question=rewritten,
            answer=answer,
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

    def _query_consensus(self, model: ModelService, question: str, context: str | None = None) -> list[dict[str, Any]]:
        from .consensus import ConsensusClient

        cfg = get_llm_config()
        query_parts = [question, model.name, model.description]
        if context:
            query_parts.append(context)
        query = " ".join(part for part in query_parts if part)
        return ConsensusClient(
            api_key=cfg.consensus_api_key,
            base_url=cfg.consensus_base_url,
        ).quick_search(query)

    def _qa_system_prompt(self) -> str:
        return (
            "You are a geospatial modeling assistant for PyGeoModel. Answer in the same language "
            "as the user's question. Use OpenGMS model metadata as the primary model-specific source. "
            "When the question requires scientific background, use your web search capability and first "
            "look for peer-reviewed scientific papers, including journal articles, conference papers, "
            "review papers, and scholarly preprints. Prefer paper resources with titles, venues, years, "
            "DOIs, and stable URLs. Official scientific documentation, standards, academic glossaries, "
            "or university materials may be used as supplementary sources, especially for constants, "
            "definitions, and units. Do not rely primarily on Wikipedia or generic web pages when "
            "scientific papers are available. When external evidence is used, include 2 to 5 relevant "
            "paper-oriented resources when available, and provide DOI or URL information in the answer. "
            "Explain uncertainty clearly. Do not merely repeat the metadata."
        )

    def _call_openai_qa(
        self,
        model: ModelService,
        question: str,
        context: str | None,
    ) -> str:
        cfg = get_llm_config()
        if not cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for model Q&A")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.openai_api_key, base_url=cfg.openai_base_url)
            completion = client.chat.completions.create(
                model=cfg.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": self._qa_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "model_metadata": model.to_dict(),
                                "notebook_context": context or "",
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                temperature=0.2,
            )
        except Exception as exc:
            message = self._sanitize_error_message(str(exc))
            raise RuntimeError(f"OpenAI Q&A request failed: {message}") from exc

        answer = completion.choices[0].message.content
        if not answer:
            raise RuntimeError("OpenAI Q&A request returned an empty answer")
        return answer

    def _sanitize_error_message(self, message: str) -> str:
        sanitized = re.sub(r"sk-[A-Za-z0-9_*-]{8,}", "sk-***", message)
        sanitized = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer ***", sanitized)
        return sanitized

    def _display_recommendation(self, recommendation: RecommendationResult) -> None:
        try:
            from IPython.display import HTML, display

            display(HTML(recommendation._repr_html_()))
        except Exception:
            print(recommendation.to_dict())

    def _load_catalog(self) -> dict[str, Any]:
        with self.data_path.open(encoding="utf-8") as fh:
            catalog = json.load(fh)
        registry_path = self._resolve_executable_registry_path()
        if registry_path is None:
            return self._attach_description_translations(catalog)
        return self._attach_description_translations(
            self._filter_catalog_by_executable_registry(catalog, registry_path)
        )

    def _resolve_executable_registry_path(self) -> Path | None:
        local_registry = self.data_path.with_name("modellist_2070.csv")
        if local_registry.exists():
            return local_registry
        if self._uses_custom_data_path:
            return None
        bundled_registry = Path(__file__).resolve().parent / "data" / "modellist_2070.csv"
        if bundled_registry.exists():
            return bundled_registry
        return None

    def _resolve_description_translations_path(self) -> Path | None:
        local_translations = self.data_path.with_name("description_translations_en.json")
        if local_translations.exists():
            return local_translations
        if self._uses_custom_data_path:
            return None
        bundled_translations = Path(__file__).resolve().parent / "data" / "description_translations_en.json"
        if bundled_translations.exists():
            return bundled_translations
        return None

    def _attach_description_translations(self, catalog: dict[str, Any]) -> dict[str, Any]:
        translations_path = self._resolve_description_translations_path()
        if translations_path is None:
            return catalog
        try:
            with translations_path.open(encoding="utf-8") as fh:
                translations = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return catalog
        if not isinstance(translations, dict):
            return catalog

        enriched: dict[str, Any] = {}
        for name, raw in catalog.items():
            raw_copy = dict(raw)
            raw_copy["_pygeomodel_description_translations_en"] = translations
            enriched[name] = raw_copy
        return enriched

    def _filter_catalog_by_executable_registry(
        self,
        catalog: dict[str, Any],
        registry_path: Path,
    ) -> dict[str, Any]:
        md5_values: set[str] = set()
        model_ids: set[str] = set()
        names: set[str] = set()
        display_by_md5: dict[str, str] = {}
        display_by_id: dict[str, str] = {}
        display_by_name: dict[str, str] = {}
        order_by_md5: dict[str, int] = {}
        order_by_id: dict[str, int] = {}
        order_by_name: dict[str, int] = {}
        with registry_path.open(encoding="utf-8-sig", newline="") as fh:
            for row_index, row in enumerate(csv.DictReader(fh), start=1):
                md5 = (row.get("MD5") or "").strip()
                model_id = (row.get("模型UID") or "").strip()
                name = (row.get("名称") or "").strip()
                display_name = (
                    row.get("display_name_en")
                    or row.get("英文显示名称")
                    or row.get("英文名称")
                    or ""
                ).strip()
                if md5:
                    md5_values.add(md5)
                    order_by_md5[md5] = row_index
                    if display_name:
                        display_by_md5[md5] = display_name
                if model_id:
                    model_ids.add(model_id)
                    order_by_id[model_id] = row_index
                    if display_name:
                        display_by_id[model_id] = display_name
                if name:
                    names.add(name)
                    order_by_name[name] = row_index
                    if display_name:
                        display_by_name[name] = display_name

        filtered: dict[str, Any] = {}
        for name, raw in catalog.items():
            raw_md5 = str(raw.get("md5") or "").strip()
            raw_id = str(raw.get("_id") or raw.get("id") or "").strip()
            raw_name = str(name or "").strip()
            if raw_md5 in md5_values or raw_id in model_ids or raw_name in names:
                display_name = display_by_md5.get(raw_md5) or display_by_id.get(raw_id) or display_by_name.get(raw_name)
                registry_order = order_by_md5.get(raw_md5) or order_by_id.get(raw_id) or order_by_name.get(raw_name) or 0
                if display_name or registry_order:
                    raw = dict(raw)
                if display_name:
                    raw["_pygeomodel_display_name"] = display_name
                if registry_order:
                    raw["_pygeomodel_registry_order"] = registry_order
                filtered[name] = raw
        return filtered

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
