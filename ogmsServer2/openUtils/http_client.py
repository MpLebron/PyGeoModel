import httpx
from typing import Optional, Dict, Any, Union, Tuple
import asyncio

# 类型别名
Headers = Dict[str, str]
Files = Dict[str, Tuple[str, Any]]


class HttpClient:
    @staticmethod
    def _make_sync_request(
        method: str,
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Files] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
        downloadFile: bool = False,
    ) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
                response = client.request(
                    method,
                    url,
                    data=data,
                    json=json,
                    files=files,
                    params=params,
                    headers=headers,
                )
                print
                response.raise_for_status()  # 检查 HTTP 错误
                if downloadFile:
                    return {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "content": response.content,
                    }
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "json": response.json(),
                }
        except httpx.TimeoutException:
            # 处理超时错误
            return {"status_code": None, "headers": None, "error": "Request timed out"}
        except httpx.HTTPStatusError as e:
            return {
                "status_code": e.response.status_code,
                "headers": dict(e.response.headers),
                "error": str(e),
            }
        except httpx.RequestError as e:
            return {
                "status_code": None,
                "headers": None,
                "error": f"Request error: {e}",
            }
        except Exception as e:
            return {
                "status_code": None,
                "headers": None,
                "error": f"Unexpected error: {e}",
            }

    @staticmethod
    def hander_response(response):
        if response["status_code"] == 200:
            return response
        else:
            raise Exception(response["error"])

    @staticmethod
    def get_sync(
        url: str,
        timeout: int = 10,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return HttpClient._make_sync_request(
            "GET", url, timeout=timeout, params=params, headers=headers
        )

    @staticmethod
    def get_file_sync(
        url: str,
        timeout: int = 10,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ):
        response = HttpClient._make_sync_request(
            "GET",
            url,
            timeout=timeout,
            params=params,
            headers=headers,
            downloadFile=True,
        )
        return response

    @staticmethod
    def post_sync(
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Files] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return HttpClient._make_sync_request(
            "POST",
            url,
            timeout=timeout,
            data=data,
            json=json,
            files=files,
            headers=headers,
        )

    @staticmethod
    def put_sync(
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return HttpClient._make_sync_request(
            "PUT", url, timeout=timeout, data=data, json=json, headers=headers
        )

    @staticmethod
    def delete_sync(
        url: str,
        timeout: int = 10,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return HttpClient._make_sync_request(
            "DELETE", url, timeout=timeout, params=params, headers=headers
        )

    @staticmethod
    async def _make_async_request(
        method: str,
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Files] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                response = await client.request(
                    method,
                    url,
                    data=data,
                    json=json,
                    files=files,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()  # 检查 HTTP 错误
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "json": response.json(),
                }
        except httpx.TimeoutException:
            # 处理超时错误
            return {"status_code": None, "headers": None, "error": "Request timed out"}
        except httpx.HTTPStatusError as e:
            return {
                "status_code": e.response.status_code,
                "headers": dict(e.response.headers),
                "error": str(e),
            }
        except httpx.RequestError as e:
            return {
                "status_code": None,
                "headers": None,
                "error": f"Request error: {e}",
            }
        except Exception as e:
            return {
                "status_code": None,
                "headers": None,
                "error": f"Unexpected error: {e}",
            }

    @staticmethod
    async def get_async(
        url: str,
        timeout: int = 10,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return await HttpClient._make_async_request(
            "GET", url, timeout=timeout, params=params, headers=headers
        )

    @staticmethod
    async def post_async(
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Files] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return await HttpClient._make_async_request(
            "POST",
            url,
            timeout=timeout,
            data=data,
            json=json,
            files=files,
            headers=headers,
        )

    @staticmethod
    async def put_async(
        url: str,
        timeout: int = 10,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return await HttpClient._make_async_request(
            "PUT", url, timeout=timeout, data=data, json=json, headers=headers
        )

    @staticmethod
    async def delete_async(
        url: str,
        timeout: int = 10,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Headers] = None,
    ) -> Dict[str, Any]:
        return await HttpClient._make_async_request(
            "DELETE", url, timeout=timeout, params=params, headers=headers
        )
