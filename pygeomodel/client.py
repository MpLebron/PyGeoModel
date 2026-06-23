"""OpenGMS service client."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import requests

from .config import OpenGMSConfig, get_opengms_config


PUBLIC_DATA_DOWNLOAD_HOST = "geomodeling.njnu.edu.cn"
PUBLIC_DATA_DOWNLOAD_PREFIX = "/dataTransferServer"
INTERNAL_DATA_DOWNLOAD_HOSTS = {"221.224.35.86:38083"}


class OpenGMSClient:
    """Thin client around OpenGMS model-service endpoints."""

    def __init__(self, token: str | None = None, config: OpenGMSConfig | None = None):
        cfg = config or get_opengms_config()
        self.token = token if token is not None else cfg.token
        self.portal_url = cfg.portal_url.rstrip("/")
        self.manager_url = cfg.manager_url.rstrip("/")
        self.data_url = cfg.data_url.rstrip("/")

    def validate_token(self) -> bool:
        if not self.token:
            return False
        response = requests.get(
            f"{self.portal_url}/sdk/check_test/",
            params={"token": self.token},
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("data") == 1

    def check_model(self, model_name: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.portal_url}/computableModel/ModelInfo_name/{quote(model_name)}",
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def check_model_service(self, model_name: str) -> bool:
        model_data = self.check_model(model_name)
        md5 = model_data.get("md5")
        if not md5:
            return False
        response = requests.get(
            f"{self.manager_url}/GeoModeling/task/verify/{md5}",
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("data") is True

    def upload_file(self, path: str | Path) -> str:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))
        with file_path.open("rb") as fh:
            response = requests.post(
                f"{self.data_url}/data/",
                files={"datafile": (file_path.name, fh)},
                timeout=60,
            )
        response.raise_for_status()
        data = response.json().get("data", {})
        data_id = data.get("id")
        if not data_id:
            raise RuntimeError("OpenGMS upload response did not include a data id")
        return f"{self.data_url}/data/{data_id}"

    def create_task(self, model_name: str, params: dict[str, Any], wait: bool = True) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("OGMS_TOKEN is required to invoke OpenGMS model services")
        from ogmsServer2 import constants as C
        from ogmsServer2 import openModel

        C.basePortalUrl = self.portal_url
        C.baseManagerUrl = self.manager_url
        C.baseDataUrl = self.data_url

        start = time.time()
        access = openModel.OGMSAccess(modelName=model_name, token=self.token)
        outputs = access.createTask(params=params) if wait else []
        return {
            "task_id": getattr(access, "task_id", None),
            "status": "completed" if wait else "submitted",
            "outputs": outputs or [],
            "execution_time": time.time() - start,
        }

    def wait_for_task(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError("Direct wait by task id is not yet exposed by OpenGMS SDK")

    def download_outputs(self, outputs: list[dict[str, Any]], output_dir: str | Path) -> list[str]:
        return download_output_files(outputs, output_dir)


def download_output_files(outputs: list[dict[str, Any]], output_dir: str | Path) -> list[str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    for index, output in enumerate(outputs):
        url = output.get("url")
        if not url:
            continue
        url = normalize_download_url(url)
        suffix = output.get("suffix") or "dat"
        tag = output.get("tag") or output.get("event") or f"output_{index + 1}"
        target = output_path / f"{tag}.{suffix}"
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        target.write_bytes(response.content)
        downloaded.append(str(target))
    return downloaded


def normalize_download_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in INTERNAL_DATA_DOWNLOAD_HOSTS and parsed.path.startswith("/data/"):
        return urlunparse(
            (
                "https",
                PUBLIC_DATA_DOWNLOAD_HOST,
                f"{PUBLIC_DATA_DOWNLOAD_PREFIX}{parsed.path}",
                "",
                parsed.query,
                parsed.fragment,
            )
        )
    return url
