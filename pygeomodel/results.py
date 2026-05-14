"""Structured records returned by PyGeoModel APIs."""

from __future__ import annotations

import json
import html
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _write_json(payload: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


@dataclass
class TaskResult:
    model_name: str
    status: str = "unknown"
    outputs: list[dict[str, Any]] = field(default_factory=list)
    downloaded_outputs: list[str] = field(default_factory=list)
    task_id: str | None = None
    model_id: str | None = None
    model_md5: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    uploaded_inputs: dict[str, Any] = field(default_factory=dict)
    endpoint: str | None = None
    pygeomodel_version: str = "1.0.14"
    execution_time: float | None = None
    record_path: str | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> str:
        self.record_path = str(path)
        return _write_json(self.to_dict(), path)

    def download(self, output_dir: str | Path) -> list[str]:
        from .client import download_output_files

        self.downloaded_outputs = download_output_files(self.outputs, output_dir)
        return self.downloaded_outputs

    def save(
        self,
        output_dir: str | Path | None = None,
        record_path: str | Path | None = None,
    ) -> list[str]:
        if output_dir is not None:
            self.download(output_dir)
        if record_path is not None:
            self.to_json(record_path)
        return self.downloaded_outputs

    def _repr_markdown_(self) -> str:
        return f"Model run: {self.model_name}\n\nStatus: {self.status}\n\nTask ID: {self.task_id or 'Not returned'}"

    def _repr_html_(self) -> str:
        return _task_result_to_html(self)


@dataclass
class RecommendationResult:
    primary_model: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    recommended_data: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> str:
        return _write_json(self.to_dict(), path)

    def _repr_markdown_(self) -> str:
        primary_name = self.primary_model.get("name") or "No primary model"
        candidate_count = len(self.candidates)
        return f"Recommended model: {primary_name}\n\nCandidate models: {candidate_count}"

    def _repr_html_(self) -> str:
        return _recommendation_to_html(self)


@dataclass
class QAResult:
    question: str
    answer: str
    model_name: str
    rewritten_question: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> str:
        return _write_json(self.to_dict(), path)

    def _repr_markdown_(self) -> str:
        return self.answer

    def _repr_html_(self) -> str:
        answer_html = _answer_to_html(self.answer)
        source_items = _format_sources(self.sources, self.answer)
        source_html = "".join(source_items) if source_items else "<li>No sources recorded.</li>"

        return f"""
        <style>
        .pygeomodel-qa-card {{
            font-family: PingFang SC, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #1e293b;
            border: 1px solid #dbe3ef;
            border-radius: 8px;
            background: #ffffff;
            overflow: hidden;
            max-width: 100%;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }}
        .pygeomodel-qa-card * {{ box-sizing: border-box; }}
        .pygeomodel-qa-answer {{
            padding: 16px;
            line-height: 1.65;
            font-size: 14px;
            overflow-wrap: anywhere;
        }}
        .pygeomodel-qa-answer h1,
        .pygeomodel-qa-answer h2,
        .pygeomodel-qa-answer h3 {{
            margin: 16px 0 8px 0;
            color: #0f172a;
            font-weight: 700;
        }}
        .pygeomodel-qa-answer h1 {{ font-size: 19px; }}
        .pygeomodel-qa-answer h2 {{ font-size: 17px; }}
        .pygeomodel-qa-answer h3 {{ font-size: 15px; }}
        .pygeomodel-qa-answer p {{ margin: 8px 0; }}
        .pygeomodel-qa-answer ul,
        .pygeomodel-qa-answer ol {{ margin: 8px 0 8px 22px; padding: 0; }}
        .pygeomodel-qa-answer li {{ margin: 4px 0; }}
        .pygeomodel-qa-answer code {{
            background: #f1f5f9;
            color: #0f172a;
            border-radius: 4px;
            padding: 1px 4px;
            font-size: 12px;
        }}
        .pygeomodel-qa-math-block {{
            margin: 12px 0;
            padding: 12px 14px;
            text-align: center;
            background: #f8fafc;
            border: 1px solid #dbe3ef;
            border-radius: 6px;
            color: #0f172a;
            font-family: "Times New Roman", STIXGeneral, "Cambria Math", serif;
            font-size: 18px;
            line-height: 1.5;
            overflow-x: auto;
        }}
        .pygeomodel-qa-math-inline {{
            display: inline-block;
            padding: 1px 5px;
            margin: 0 1px;
            border-radius: 4px;
            background: #f8fafc;
            color: #0f172a;
            font-family: "Times New Roman", STIXGeneral, "Cambria Math", serif;
            line-height: 1.35;
            max-width: 100%;
            white-space: normal;
        }}
        .pygeomodel-qa-frac {{
            display: inline-grid;
            grid-template-rows: auto auto;
            vertical-align: middle;
            text-align: center;
            margin: 0 2px;
            line-height: 1.05;
        }}
        .pygeomodel-qa-frac-num {{
            border-bottom: 1px solid currentColor;
            padding: 0 3px 1px 3px;
        }}
        .pygeomodel-qa-frac-den {{
            padding: 1px 3px 0 3px;
        }}
        .pygeomodel-qa-sources {{
            padding: 12px 16px;
            border-top: 1px solid #e5edf6;
            background: #fbfdff;
        }}
        .pygeomodel-qa-sources h4 {{
            margin: 0 0 8px 0;
            color: #0f172a;
            font-size: 13px;
        }}
        .pygeomodel-qa-sources ul {{
            margin: 0;
            padding-left: 18px;
            color: #475569;
            font-size: 12px;
            line-height: 1.5;
        }}
        .pygeomodel-qa-sources a {{
            color: #1d4ed8;
            text-decoration: none;
            overflow-wrap: anywhere;
        }}
        .pygeomodel-qa-sources a:hover {{ text-decoration: underline; }}
        </style>
        <div class="pygeomodel-qa-card">
            <div class="pygeomodel-qa-answer">{answer_html}</div>
            <div class="pygeomodel-qa-sources">
                <h4>Sources</h4>
                <ul>{source_html}</ul>
            </div>
        </div>
        """


def _task_result_to_html(result: TaskResult) -> str:
    status = html.escape(str(result.status or "unknown"))
    status_class = "success" if status.lower() == "completed" else "neutral"
    task_id = html.escape(str(result.task_id or "Not returned"))
    runtime = _format_seconds(result.execution_time)
    record_path = html.escape(str(result.record_path or "Not saved"))
    endpoint = html.escape(str(result.endpoint or "Not recorded"))
    output_count = len(result.outputs or [])
    downloaded_count = len(result.downloaded_outputs or [])
    outputs_html = _task_outputs_to_html(result.outputs or [])
    downloaded_html = _downloaded_outputs_to_html(result.downloaded_outputs or [])
    params_json = html.escape(json.dumps(result.params or {}, ensure_ascii=False, indent=2), quote=False)
    uploaded_json = html.escape(json.dumps(result.uploaded_inputs or {}, ensure_ascii=False, indent=2), quote=False)

    return f"""
    <style>
    .pygeomodel-task-card {{
        font-family: PingFang SC, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #1e293b;
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        background: #ffffff;
        overflow: hidden;
        max-width: 100%;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .pygeomodel-task-card * {{ box-sizing: border-box; }}
    .pygeomodel-task-head {{
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 16px 18px;
        border-bottom: 1px solid #e5edf6;
        background: #fbfdff;
    }}
    .pygeomodel-task-status {{
        flex: 0 0 auto;
        min-width: 88px;
        text-align: center;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        line-height: 1.5;
        font-weight: 750;
        border: 1px solid #cbd5e1;
        color: #475569;
        background: #f8fafc;
    }}
    .pygeomodel-task-status.success {{
        border-color: #bbf7d0;
        color: #15803d;
        background: #f0fdf4;
    }}
    .pygeomodel-task-title {{
        min-width: 0;
    }}
    .pygeomodel-task-title h4 {{
        margin: 0;
        color: #0f172a;
        font-size: 15px;
        line-height: 1.4;
        font-weight: 750;
    }}
    .pygeomodel-task-title p {{
        margin: 4px 0 0 0;
        color: #64748b;
        font-size: 12px;
        line-height: 1.5;
    }}
    .pygeomodel-task-body {{
        padding: 14px 18px 16px 18px;
    }}
    .pygeomodel-task-meta {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 10px;
        margin-bottom: 16px;
    }}
    .pygeomodel-task-meta div {{
        border-top: 1px solid #e5edf6;
        padding-top: 8px;
    }}
    .pygeomodel-task-meta b {{
        display: block;
        color: #475569;
        font-size: 11px;
        line-height: 1.4;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }}
    .pygeomodel-task-meta span {{
        display: block;
        margin-top: 3px;
        color: #0f172a;
        font-size: 12px;
        line-height: 1.45;
        overflow-wrap: anywhere;
    }}
    .pygeomodel-task-section {{
        margin-top: 14px;
    }}
    .pygeomodel-task-section h4 {{
        margin: 0 0 8px 0;
        color: #0f172a;
        font-size: 14px;
        line-height: 1.4;
        font-weight: 750;
    }}
    .pygeomodel-task-table {{
        display: grid;
        grid-template-columns: minmax(180px, 1.1fr) minmax(140px, 0.8fr) minmax(100px, 0.55fr) minmax(150px, 0.8fr);
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        overflow: hidden;
        font-size: 12px;
        line-height: 1.45;
    }}
    .pygeomodel-task-table > div {{
        padding: 9px 11px;
        border-bottom: 1px solid #e8eef6;
        overflow-wrap: anywhere;
    }}
    .pygeomodel-task-table .head {{
        background: #f8fafc;
        color: #475569;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-size: 11px;
    }}
    .pygeomodel-task-table .muted {{
        color: #94a3b8;
    }}
    .pygeomodel-task-table a {{
        color: #1d4ed8;
        text-decoration: none;
    }}
    .pygeomodel-task-table a:hover {{ text-decoration: underline; }}
    .pygeomodel-task-details {{
        margin-top: 14px;
        border-top: 1px solid #e5edf6;
        padding-top: 10px;
        color: #334155;
        font-size: 12px;
    }}
    .pygeomodel-task-details summary {{
        cursor: pointer;
        font-weight: 700;
    }}
    .pygeomodel-task-details pre {{
        margin: 10px 0 0 0;
        padding: 10px;
        border-radius: 6px;
        background: #f8fafc;
        border: 1px solid #e5edf6;
        color: #0f172a;
        font-size: 11px;
        line-height: 1.45;
        overflow-x: auto;
        white-space: pre-wrap;
    }}
    @media (max-width: 840px) {{
        .pygeomodel-task-head {{
            display: block;
        }}
        .pygeomodel-task-status {{
            display: inline-block;
            margin-bottom: 10px;
        }}
        .pygeomodel-task-table {{
            grid-template-columns: minmax(120px, 1fr) minmax(120px, 1fr);
        }}
    }}
    </style>
    <div class="pygeomodel-task-card">
        <div class="pygeomodel-task-head">
            <span class="pygeomodel-task-status {status_class}">{status}</span>
            <div class="pygeomodel-task-title">
                <h4>Model Execution Summary</h4>
                <p>{html.escape(result.model_name)}</p>
            </div>
        </div>
        <div class="pygeomodel-task-body">
            <div class="pygeomodel-task-meta">
                <div><b>Task ID</b><span>{task_id}</span></div>
                <div><b>Runtime</b><span>{html.escape(runtime)}</span></div>
                <div><b>Output resources</b><span>{output_count}</span></div>
                <div><b>Saved output files</b><span>{downloaded_count}</span></div>
                <div><b>Execution record</b><span>{record_path}</span></div>
                <div><b>Endpoint</b><span>{endpoint}</span></div>
                <div><b>PyGeoModel</b><span>{html.escape(str(result.pygeomodel_version))}</span></div>
            </div>
            <div class="pygeomodel-task-section">
                <h4>Output resources</h4>
                {outputs_html}
            </div>
            <div class="pygeomodel-task-section">
                <h4>Saved output files</h4>
                {downloaded_html}
            </div>
            <details class="pygeomodel-task-details">
                <summary>Input parameters</summary>
                <pre>{params_json}</pre>
            </details>
            <details class="pygeomodel-task-details">
                <summary>Uploaded input structure</summary>
                <pre>{uploaded_json}</pre>
            </details>
        </div>
    </div>
    """


def _task_outputs_to_html(outputs: list[dict[str, Any]]) -> str:
    if not outputs:
        return '<div class="pygeomodel-task-table"><div class="muted">No output resources were returned.</div></div>'

    rows = [
        '<div class="head">Name</div>',
        '<div class="head">State</div>',
        '<div class="head">Format</div>',
        '<div class="head">Access</div>',
    ]
    for output in outputs:
        name = html.escape(str(output.get("tag") or output.get("event") or "Output"))
        state = html.escape(str(output.get("statename") or ""))
        suffix = html.escape(str(output.get("suffix") or "Not specified"))
        url = str(output.get("url") or "")
        if url:
            safe_url = html.escape(url)
            access = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">Open output</a>'
        else:
            access = '<span class="muted">No downloadable URL returned</span>'
        rows.extend([f"<div>{name}</div>", f"<div>{state}</div>", f"<div>{suffix}</div>", f"<div>{access}</div>"])
    return f'<div class="pygeomodel-task-table">{"".join(rows)}</div>'


def _downloaded_outputs_to_html(paths: list[str]) -> str:
    if not paths:
        return (
            '<div class="pygeomodel-task-table">'
            '<div class="muted">No output files were downloaded. This can happen when the OpenGMS service returns output metadata without a downloadable URL.</div>'
            '</div>'
        )

    rows = [
        '<div class="head">File</div>',
        '<div class="head">Location</div>',
        '<div class="head">Status</div>',
        '<div class="head">Access</div>',
    ]
    for path in paths:
        safe_path = html.escape(str(path))
        name = html.escape(Path(path).name)
        rows.extend([
            f"<div>{name}</div>",
            f"<div>{safe_path}</div>",
            "<div>Saved</div>",
            "<div>Local file</div>",
        ])
    return f'<div class="pygeomodel-task-table">{"".join(rows)}</div>'


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "Not recorded"
    if value < 60:
        return f"{value:.2f} s"
    minutes = int(value // 60)
    seconds = value - minutes * 60
    return f"{minutes} min {seconds:.1f} s"


def _recommendation_to_html(result: RecommendationResult) -> str:
    candidates = result.candidates or []
    recommended_data = result.recommended_data or {}

    candidate_rows = "".join(_recommendation_candidate_row(candidate) for candidate in candidates)
    if not candidate_rows:
        candidate_rows = '<div class="pygeomodel-rec-empty">No candidate models were returned.</div>'

    local_data_html = _recommendation_data_items(recommended_data.get("local_data", []), label_key="location")
    kb_data_html = _recommendation_data_items(recommended_data.get("knowledge_base_data", []), label_key="url")

    return f"""
    <style>
    .pygeomodel-rec-card {{
        font-family: PingFang SC, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #1e293b;
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        background: #ffffff;
        overflow: hidden;
        max-width: 100%;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .pygeomodel-rec-card * {{ box-sizing: border-box; }}
    .pygeomodel-rec-body {{
        padding: 16px 18px 18px 18px;
    }}
    .pygeomodel-rec-section {{
        margin-top: 16px;
    }}
    .pygeomodel-rec-section:first-child {{
        margin-top: 0;
    }}
    .pygeomodel-rec-section h4 {{
        margin: 0 0 10px 0;
        color: #0f172a;
        font-size: 14px;
        line-height: 1.4;
        font-weight: 750;
    }}
    .pygeomodel-rec-list {{
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        overflow: hidden;
        background: #ffffff;
    }}
    .pygeomodel-rec-list-head,
    .pygeomodel-rec-row {{
        display: grid;
        grid-template-columns: 90px minmax(220px, 0.95fr) minmax(280px, 1.25fr) minmax(220px, 1fr);
        column-gap: 18px;
        align-items: start;
    }}
    .pygeomodel-rec-list-head {{
        padding: 9px 14px;
        background: #f8fafc;
        border-bottom: 1px solid #dbe3ef;
        color: #475569;
        font-size: 11px;
        font-weight: 750;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }}
    .pygeomodel-rec-row {{
        padding: 13px 14px;
        border-bottom: 1px solid #e8eef6;
    }}
    .pygeomodel-rec-row:last-child {{
        border-bottom: 0;
    }}
    .pygeomodel-rec-row.primary {{
        background: #f8fbff;
        box-shadow: inset 3px 0 0 #60a5fa;
    }}
    .pygeomodel-rec-rank {{
        color: #64748b;
        font-size: 12px;
        font-weight: 750;
        line-height: 1.4;
        white-space: nowrap;
    }}
    .pygeomodel-rec-name {{
        color: #0f172a;
        font-size: 13px;
        line-height: 1.35;
        font-weight: 750;
    }}
    .pygeomodel-rec-description,
    .pygeomodel-rec-text {{
        margin: 0;
        color: #475569;
        font-size: 12px;
        line-height: 1.5;
    }}
    .pygeomodel-rec-description {{
        margin-top: 5px;
    }}
    .pygeomodel-rec-muted {{
        color: #94a3b8;
    }}
    .pygeomodel-rec-data-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 12px;
    }}
    .pygeomodel-rec-data-block {{
        border-top: 1px solid #e5edf6;
        padding-top: 10px;
    }}
    .pygeomodel-rec-data-block h5 {{
        margin: 0 0 8px 0;
        color: #334155;
        font-size: 12px;
        font-weight: 750;
    }}
    .pygeomodel-rec-data-block ul {{
        margin: 0;
        padding-left: 18px;
        color: #475569;
        font-size: 12px;
        line-height: 1.5;
    }}
    .pygeomodel-rec-data-block a {{
        color: #1d4ed8;
        text-decoration: none;
        overflow-wrap: anywhere;
    }}
    .pygeomodel-rec-empty {{
        color: #64748b;
        font-size: 12px;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        padding: 12px;
        background: #f8fafc;
    }}
    @media (max-width: 900px) {{
        .pygeomodel-rec-list-head {{
            display: none;
        }}
        .pygeomodel-rec-row {{
            grid-template-columns: 76px minmax(0, 1fr);
            row-gap: 8px;
        }}
        .pygeomodel-rec-row > div:nth-child(3),
        .pygeomodel-rec-row > div:nth-child(4) {{
            grid-column: 2;
        }}
    }}
    </style>
    <div class="pygeomodel-rec-card">
        <div class="pygeomodel-rec-body">
            <div class="pygeomodel-rec-section">
                <div class="pygeomodel-rec-list">
                    <div class="pygeomodel-rec-list-head">
                        <div>Rank</div>
                        <div>Candidate model</div>
                        <div>Recommendation rationale</div>
                        <div>Input data</div>
                    </div>
                    {candidate_rows}
                </div>
            </div>
            <div class="pygeomodel-rec-section">
                <h4>Relevant Data</h4>
                <div class="pygeomodel-rec-data-grid">
                    <div class="pygeomodel-rec-data-block">
                        <h5>Local data</h5>
                        <ul>{local_data_html}</ul>
                    </div>
                    <div class="pygeomodel-rec-data-block">
                        <h5>Knowledge-base data</h5>
                        <ul>{kb_data_html}</ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def _recommendation_candidate_row(candidate: dict[str, Any]) -> str:
    name = html.escape(str(candidate.get("name") or "Unnamed model"))
    description = html.escape(str(candidate.get("description") or candidate.get("desc") or ""))
    reason = html.escape(str(candidate.get("reason") or candidate.get("recommendation_reason") or ""))
    input_desc = html.escape(str(candidate.get("brief_input_data_desc") or candidate.get("briefInputDataDesc") or ""))
    rank = html.escape(str(candidate.get("rank") or ""))
    is_primary = bool(candidate.get("is_primary"))
    primary_class = " primary" if is_primary else ""
    rank_label = f"&#9733; Rank {rank}" if is_primary else f"Rank {rank}"

    return f"""
    <div class="pygeomodel-rec-row{primary_class}">
        <div class="pygeomodel-rec-rank">
            {rank_label}
        </div>
        <div>
            <div class="pygeomodel-rec-name">{name}</div>
            {f'<p class="pygeomodel-rec-description">{description}</p>' if description else ''}
        </div>
        <p class="pygeomodel-rec-text">{reason if reason else '<span class="pygeomodel-rec-muted">No recommendation rationale recorded.</span>'}</p>
        <p class="pygeomodel-rec-text">{input_desc if input_desc else '<span class="pygeomodel-rec-muted">No input-data description recorded.</span>'}</p>
    </div>
    """


def _recommendation_data_items(items: Any, label_key: str) -> str:
    if not isinstance(items, list) or not items:
        return "<li>No data resources recorded.</li>"

    rendered: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            rendered.append(f"<li>{html.escape(str(item))}</li>")
            continue
        name = html.escape(str(item.get("name") or "Unnamed data"))
        label = item.get(label_key) or item.get("url") or item.get("location") or ""
        if label_key == "url" and label:
            safe_url = html.escape(str(label))
            rendered.append(f'<li><b>{name}</b>: <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a></li>')
        elif label:
            rendered.append(f"<li><b>{name}</b>: {html.escape(str(label))}</li>")
        else:
            rendered.append(f"<li><b>{name}</b></li>")
    return "".join(rendered)


def _answer_to_html(text: str) -> str:
    text = text or ""
    placeholders: dict[str, str] = {}
    protected_text = _protect_math_expressions(text, placeholders)
    html_text = _markdown_to_html(protected_text)
    for token, replacement in placeholders.items():
        html_text = html_text.replace(token, replacement)
    html_text = re.sub(
        r"<p>\s*(<div class=\"pygeomodel-qa-math-block\">.*?</div>)\s*</p>",
        r"\1",
        html_text,
        flags=re.DOTALL,
    )
    return _linkify_urls(html_text)


def _markdown_to_html(text: str) -> str:
    try:
        import markdown

        escaped = html.escape(text or "", quote=False)
        return markdown.markdown(escaped, extensions=["extra", "sane_lists"])
    except Exception:
        paragraphs = [f"<p>{html.escape(part)}</p>" for part in (text or "").split("\n\n") if part.strip()]
        return "".join(paragraphs)


def _format_sources(sources: list[dict[str, Any]], answer: str) -> list[str]:
    items: list[str] = []
    for source in sources:
        raw_type = str(source.get("type", "Source"))
        if raw_type == "OpenGMS metadata":
            raw_type = "OpenGMS Knowledge Base"
        source_type = html.escape(raw_type)
        label = html.escape(str(source.get("title") or source.get("model") or source.get("name") or source_type))
        url = source.get("url") or source.get("doi")
        if url:
            safe_url = html.escape(str(url))
            items.append(f'<li><b>{source_type}</b>: <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{label}</a></li>')
        else:
            items.append(f"<li><b>{source_type}</b>: {label}</li>")

    seen = {str(source.get("url") or source.get("doi") or "") for source in sources}
    for url in re.findall(r"https?://[^\s)>\]]+", answer or ""):
        clean_url = url.rstrip(".,;")
        if clean_url in seen:
            continue
        seen.add(clean_url)
        safe_url = html.escape(clean_url)
        items.append(f'<li><b>Web source</b>: <a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a></li>')
    return items


def _protect_math_expressions(text: str, placeholders: dict[str, str]) -> str:
    protected = text

    def block_replacement(match):
        content = next(group for group in match.groups() if group is not None)
        return _store_placeholder(placeholders, _render_math(content, block=True))

    block_patterns = [
        r"\$\$\s*(.*?)\s*\$\$",
        r"\\\[\s*(.*?)\s*\\\]",
        r"(?m)^[ \t]*\[[ \t]*(.+?)[ \t]*\][ \t]*$",
    ]
    for pattern in block_patterns:
        protected = re.sub(
            pattern,
            lambda match: block_replacement(match) if _looks_like_math(next(group for group in match.groups() if group is not None)) else match.group(0),
            protected,
            flags=re.DOTALL if "$$" in pattern or "\\[" in pattern else 0,
        )

    inline_patterns = [
        r"\\\((.+?)\\\)",
        r"\$(.+?)\$",
        r"\((\\(?:rho|alpha|beta|gamma|Delta|frac|text|cdot|times)[^)]+)\)",
    ]
    for pattern in inline_patterns:
        protected = re.sub(
            pattern,
            lambda match: _store_placeholder(placeholders, _render_math(match.group(1), block=False))
            if _looks_like_math(match.group(1))
            else match.group(0),
            protected,
        )
    return protected


def _store_placeholder(placeholders: dict[str, str], html_value: str) -> str:
    token = f"PYGEOMODEL_MATH_{len(placeholders)}"
    placeholders[token] = html_value
    return token


def _render_math(value: str, block: bool) -> str:
    content = _format_math_text(value)
    class_name = "pygeomodel-qa-math-block" if block else "pygeomodel-qa-math-inline"
    return f'<span class="{class_name}">{content}</span>' if not block else f'<div class="{class_name}">{content}</div>'


def _format_math_text(value: str) -> str:
    text = _strip_math_delimiters(value)
    text = html.escape(text, quote=False)

    text = re.sub(r"\\(?:text|mathrm)\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", _format_fraction, text)

    replacements = {
        r"\rho": "ρ",
        r"\alpha": "α",
        r"\beta": "β",
        r"\gamma": "γ",
        r"\Delta": "Δ",
        r"\theta": "θ",
        r"\lambda": "λ",
        r"\mu": "μ",
        r"\sigma": "σ",
        r"\times": "×",
        r"\cdot": "·",
        r"\approx": "≈",
        r"\leq": "≤",
        r"\geq": "≥",
        r"\pm": "±",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\^\{([^{}]+)\}", r"<sup>\1</sup>", text)
    text = re.sub(r"\^(-?\d+)", r"<sup>\1</sup>", text)
    text = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", text)
    text = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", text)
    text = text.replace("\\", "")
    return text.strip()


def _format_fraction(match) -> str:
    numerator = _format_math_text(match.group(1))
    denominator = _format_math_text(match.group(2))
    return (
        '<span class="pygeomodel-qa-frac">'
        f'<span class="pygeomodel-qa-frac-num">{numerator}</span>'
        f'<span class="pygeomodel-qa-frac-den">{denominator}</span>'
        '</span>'
    )


def _strip_math_delimiters(value: str) -> str:
    text = (value or "").strip()
    pairs = [
        ("$$", "$$"),
        (r"\[", r"\]"),
        (r"\(", r"\)"),
        ("[", "]"),
        ("$", "$"),
    ]
    changed = True
    while changed:
        changed = False
        for left, right in pairs:
            if text.startswith(left) and text.endswith(right):
                text = text[len(left): len(text) - len(right)].strip()
                changed = True
    return text


def _linkify_urls(html_text: str) -> str:
    return re.sub(
        r"(?<![\"'>])(https?://[^\s<]+)",
        lambda match: f'<a href="{html.escape(match.group(1).rstrip(".,;"))}" target="_blank" rel="noopener noreferrer">{html.escape(match.group(1).rstrip(".,;"))}</a>',
        html_text,
    )


def _looks_like_math(value: str) -> bool:
    math_tokens = ("=", "\\", "^", "_", "frac", "rho", "times", "cdot", "mol", "text")
    return any(token in value for token in math_tokens)
