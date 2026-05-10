"""Configuration helpers for PyGeoModel."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
    dify_api_key: str | None = None
    dify_base_url: str = "https://api.dify.ai/v1"


def get_opengms_config() -> OpenGMSConfig:
    return OpenGMSConfig(
        token=os.environ.get("OGMS_TOKEN"),
        portal_url=os.environ.get("OGMS_BASE_PORTAL_URL", OpenGMSConfig.portal_url),
        manager_url=os.environ.get("OGMS_BASE_MANAGER_URL", OpenGMSConfig.manager_url),
        data_url=os.environ.get("OGMS_BASE_DATA_URL", OpenGMSConfig.data_url),
    )


def get_llm_config() -> LLMConfig:
    return LLMConfig(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", LLMConfig.openai_base_url),
        dify_api_key=os.environ.get("DIFY_API_KEY"),
        dify_base_url=os.environ.get("DIFY_BASE_URL", LLMConfig.dify_base_url),
    )
