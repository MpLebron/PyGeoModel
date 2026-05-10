"""Structured records returned by PyGeoModel APIs."""

from __future__ import annotations

import json
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
    task_id: str | None = None
    model_id: str | None = None
    model_md5: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    uploaded_inputs: dict[str, Any] = field(default_factory=dict)
    endpoint: str | None = None
    pygeomodel_version: str = "1.0.4"
    execution_time: float | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> str:
        return _write_json(self.to_dict(), path)

    def download(self, output_dir: str | Path) -> list[str]:
        from .client import download_output_files

        return download_output_files(self.outputs, output_dir)


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
