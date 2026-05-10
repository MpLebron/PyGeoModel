"""Model catalog and metadata objects."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def normalize_optional(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _first_data_item(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or []
    return data[0] if data and isinstance(data[0], dict) else {}


def _flatten_leaf_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for node in nodes:
        nested = node.get("nodes")
        if isinstance(nested, list) and nested:
            leaves.extend(_flatten_leaf_nodes(nested))
        else:
            leaves.append(node)
    return leaves


@dataclass
class ModelSummary:
    name: str
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    model_id: str = ""
    md5: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelInput:
    state: str
    name: str
    event_name: str
    data_type: str = "STRING"
    required: bool = True
    description: str = ""
    is_file: bool = False
    children: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelOutput:
    state: str
    name: str
    event_name: str
    data_type: str = "unknown"
    description: str = ""
    children: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelService:
    name: str
    raw: dict[str, Any]
    model_id: str = ""
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    tags_en: list[str] = field(default_factory=list)
    md5: str = ""
    states: list[dict[str, Any]] = field(default_factory=list)
    inputs: list[ModelInput] = field(default_factory=list)
    outputs: list[ModelOutput] = field(default_factory=list)

    @classmethod
    def from_raw(cls, name: str, raw: dict[str, Any]) -> "ModelService":
        mdl = raw.get("mdlJson", {}).get("mdl", {})
        states = mdl.get("states", [])
        service = cls(
            name=name,
            raw=raw,
            model_id=raw.get("_id", raw.get("id", "")),
            description=raw.get("description", ""),
            author=raw.get("author", ""),
            tags=list(raw.get("normalTags", []) or []),
            tags_en=list(raw.get("normalTagsEn", []) or []),
            md5=raw.get("md5", ""),
            states=states,
        )
        service.inputs = service._parse_inputs()
        service.outputs = service._parse_outputs()
        return service

    def summary(self) -> ModelSummary:
        return ModelSummary(
            name=self.name,
            description=self.description,
            author=self.author,
            tags=self.tags,
            model_id=self.model_id,
            md5=self.md5,
        )

    def describe(self) -> str:
        return self.description

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_id": self.model_id,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "tags_en": self.tags_en,
            "md5": self.md5,
            "states": self.states,
            "inputs": [item.to_dict() for item in self.inputs],
            "outputs": [item.to_dict() for item in self.outputs],
        }

    def to_json(self, path: str | Path) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_path)

    def normalize_params(self, params: dict[str, Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for item in self.inputs:
            if item.event_name in normalized.get(item.state, {}):
                continue
            value, found = self._value_for_input(item, params)
            if not found:
                if item.required:
                    missing.append(item.name)
                continue
            normalized.setdefault(item.state, {})[item.event_name] = self._convert_value(value, item)
        if missing:
            raise ValueError(f"Missing required model parameters: {', '.join(missing)}")
        return normalized

    def _value_for_input(self, item: ModelInput, params: dict[str, Any]) -> tuple[Any, bool]:
        if item.event_name in params:
            return params[item.event_name], True
        if item.name in params:
            return params[item.name], True
        return None, False

    def _convert_value(self, value: Any, item: ModelInput) -> Any:
        if item.is_file:
            return str(value)
        dtype = (item.data_type or "").upper()
        if dtype in {"REAL", "DOUBLE", "FLOAT"}:
            return float(value)
        if dtype in {"INT", "INTEGER"}:
            return int(value)
        if dtype in {"BOOL", "BOOLEAN"}:
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "y"}
            return bool(value)
        return value

    def _parse_inputs(self) -> list[ModelInput]:
        items: list[ModelInput] = []
        for state in self.states:
            state_name = state.get("name", "")
            for event in state.get("event", []) or []:
                if event.get("eventType") != "response":
                    continue
                items.extend(self._parse_input_event(state_name, event))
        return items

    def _parse_outputs(self) -> list[ModelOutput]:
        items: list[ModelOutput] = []
        for state in self.states:
            state_name = state.get("name", "")
            for event in state.get("event", []) or []:
                if event.get("eventType") != "noresponse":
                    continue
                data_item = _first_data_item(event)
                children = data_item.get("nodes", []) if isinstance(data_item.get("nodes"), list) else []
                items.append(
                    ModelOutput(
                        state=state_name,
                        name=event.get("eventName", ""),
                        event_name=event.get("eventName", ""),
                        data_type=data_item.get("dataType", "unknown"),
                        description=event.get("eventDesc") or data_item.get("desc", ""),
                        children=children,
                    )
                )
        return items

    def _parse_input_event(self, state_name: str, event: dict[str, Any]) -> list[ModelInput]:
        data_item = _first_data_item(event)
        event_name = event.get("eventName", "")
        required = not normalize_optional(event.get("optional", False))
        nodes = data_item.get("nodes")
        if isinstance(nodes, list) and nodes:
            leaves = _flatten_leaf_nodes(nodes)
            return [
                ModelInput(
                    state=state_name,
                    name=node.get("text", event_name),
                    event_name=event_name if len(leaves) > 1 else node.get("text", event_name),
                    data_type=node.get("dataType", data_item.get("dataType", "STRING")),
                    required=required,
                    description=node.get("desc") or event.get("eventDesc", ""),
                    is_file=False,
                    children=nodes,
                )
                for node in leaves
            ]
        data_type = data_item.get("dataType", "external")
        is_file = data_type == "external" or "externalId" in data_item or not data_item
        return [
            ModelInput(
                state=state_name,
                name=event_name,
                event_name=event_name,
                data_type=data_type,
                required=required,
                description=event.get("eventDesc") or data_item.get("desc", ""),
                is_file=is_file,
            )
        ]
