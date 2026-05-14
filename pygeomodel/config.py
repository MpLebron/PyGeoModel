"""Configuration helpers for PyGeoModel."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


PUBLIC_DEMO_OGMS_TOKEN = '6U3O1Sy5696I5ryJFaYCYVjcIV7rhd1MKK0QGX9A7zafogi8xTdvejl6ISUP1lEs'
PUBLIC_DEMO_DIFY_API_KEY = 'app-CuNONc6hSct2ap07nmUgcaw9'
PUBLIC_DEMO_DIFY_BASE_URL = 'https://api.dify.ai/v1'
PUBLIC_DEMO_OPENAI_API_KEY = 'sk-4bp5a1DcdLSHCiw1401270055f47424b9eA58cAd587266A3'
PUBLIC_DEMO_OPENAI_BASE_URL = 'https://aihubmix.com/v1'
PUBLIC_DEMO_OPENAI_MODEL = 'gpt-5.2-low'


@dataclass(frozen=True)
class OpenGMSConfig:
    token: str | None = None
    portal_url: str = "http://222.192.7.75"
    manager_url: str = "http://222.192.7.75/managerServer"
    data_url: str = "http://222.192.7.75/dataTransferServer"


@dataclass(frozen=True)
class LLMConfig:
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.2-low"
    dify_api_key: str | None = None
    dify_base_url: str = "https://api.dify.ai/v1"
    consensus_api_key: str | None = None
    consensus_base_url: str = "https://api.consensus.app/v1"


def get_opengms_config() -> OpenGMSConfig:
    local = _load_local_api_keys()
    opengms = local.get("opengms", {})
    return OpenGMSConfig(
        token=os.environ.get("OGMS_TOKEN") or opengms.get("token") or opengms.get("api_key") or PUBLIC_DEMO_OGMS_TOKEN,
        portal_url=os.environ.get("OGMS_BASE_PORTAL_URL", opengms.get("portal_url", OpenGMSConfig.portal_url)),
        manager_url=os.environ.get("OGMS_BASE_MANAGER_URL", opengms.get("manager_url", OpenGMSConfig.manager_url)),
        data_url=os.environ.get("OGMS_BASE_DATA_URL", opengms.get("data_url", OpenGMSConfig.data_url)),
    )


def get_llm_config() -> LLMConfig:
    local = _load_local_api_keys()
    openai = local.get("openai", {})
    dify = local.get("dify", {})
    consensus = local.get("consensus", {})
    return LLMConfig(
        openai_api_key=os.environ.get("PYGEOMODEL_OPENAI_API_KEY") or openai.get("api_key") or PUBLIC_DEMO_OPENAI_API_KEY,
        openai_base_url=os.environ.get("PYGEOMODEL_OPENAI_BASE_URL") or openai.get("base_url") or PUBLIC_DEMO_OPENAI_BASE_URL,
        openai_model=os.environ.get("PYGEOMODEL_OPENAI_MODEL") or openai.get("model") or PUBLIC_DEMO_OPENAI_MODEL,
        dify_api_key=os.environ.get("PYGEOMODEL_DIFY_API_KEY") or dify.get("api_key") or PUBLIC_DEMO_DIFY_API_KEY,
        dify_base_url=os.environ.get("PYGEOMODEL_DIFY_BASE_URL") or dify.get("base_url") or PUBLIC_DEMO_DIFY_BASE_URL,
        consensus_api_key=consensus.get("api_key") or os.environ.get("PYGEOMODEL_CONSENSUS_API_KEY"),
        consensus_base_url=consensus.get("base_url") or os.environ.get("PYGEOMODEL_CONSENSUS_BASE_URL") or LLMConfig.consensus_base_url,
    )


def _load_local_api_keys() -> dict:
    """Load optional local credentials without making them part of package data."""
    candidates = [
        Path.cwd() / "config" / "api_keys.json",
        Path(__file__).resolve().parent.parent / "config" / "api_keys.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}
