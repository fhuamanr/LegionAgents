"""LM Studio REST API v1 client for local runtime management."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit, urlunsplit


class LMStudioClientError(ValueError):
    """Structured LM Studio client error."""

    def __init__(
        self,
        *,
        code: str,
        endpoint: str,
        status_code: int | None = None,
        response_body: str | None = None,
        suggested_action: str | None = None,
    ) -> None:
        self.code = code
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body
        self.suggested_action = suggested_action
        super().__init__(
            json.dumps(
                {
                    "error_code": code,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "response_body": response_body,
                    "suggested_action": suggested_action,
                }
            )
        )


class LMStudioClient:
    """Strict LM Studio REST API v1 client."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        headers: dict[str, str] | None = None,
        auth_mode: str = "raw",
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._api_key = (api_key or "").strip()
        self._timeout = timeout_seconds or 30
        self._headers = headers or {}
        self._auth_mode = auth_mode if auth_mode in {"raw", "bearer"} else "raw"

    def list_models(self) -> dict[str, Any]:
        return self._request_json("GET", "/api/v1/models")

    def load_model(
        self,
        model_id: str,
        *,
        context_length: int | None = None,
        flash_attention: bool = True,
        echo_load_config: bool = True,
    ) -> dict[str, Any]:
        body = {
            "model": model_id,
            "context_length": context_length,
            "flash_attention": flash_attention,
            "echo_load_config": echo_load_config,
        }
        body = {key: value for key, value in body.items() if value is not None}
        return self._request_json("POST", "/api/v1/models/load", body=body)

    def unload_model(self, instance_id: str) -> dict[str, Any]:
        return self._request_json("POST", "/api/v1/models/unload", body={"instance_id": instance_id})

    def download_model(self, model_id: str) -> dict[str, Any]:
        return self._request_json("POST", "/api/v1/models/download", body={"model": model_id})

    def download_status(self, *, model: str | None = None) -> dict[str, Any]:
        suffix = ""
        if model:
            suffix = f"?model={model}"
        return self._request_json("GET", f"/api/v1/models/download/status{suffix}")

    def chat_completion(self, *, model: str, messages: list[dict[str, str]], stream: bool = False, max_tokens: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        return self._request_json("POST", "/v1/chat/completions", body=body)

    def _request_json(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._api_key:
            raise LMStudioClientError(
                code="lm_studio_token_missing",
                endpoint=f"{self._base_url}{path}",
                suggested_action="LM Studio API token is required for model listing/loading/unloading.",
            )
        url = f"{self._base_url}{path}"
        request_body = None if body is None else json.dumps(body).encode("utf-8")
        auth_value = self._api_key if self._auth_mode == "raw" else f"Bearer {self._api_key}"
        headers = {"Accept": "application/json", **self._headers, "Authorization": auth_value}
        if request_body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=request_body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = response.read().decode("utf-8") or "{}"
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 401:
                raise LMStudioClientError(
                    code="lm_studio_token_rejected",
                    endpoint=url,
                    status_code=exc.code,
                    response_body=body_text,
                    suggested_action="LM Studio rejected the API token.",
                ) from exc
            code = {
                "/api/v1/models": "lm_studio_list_failed",
                "/api/v1/models/load": "lm_studio_load_failed",
                "/api/v1/models/unload": "lm_studio_unload_failed",
                "/api/v1/models/download": "lm_studio_download_failed",
                "/api/v1/models/download/status": "lm_studio_download_status_failed",
            }.get(path, "lm_studio_endpoint_unavailable")
            raise LMStudioClientError(
                code=code,
                endpoint=url,
                status_code=exc.code,
                response_body=body_text,
                suggested_action="Validate LM Studio endpoint availability and payload compatibility.",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise LMStudioClientError(
                code="lm_studio_endpoint_unavailable",
                endpoint=url,
                response_body=str(exc),
                suggested_action="Verify LM Studio base URL and that REST API server is running.",
            ) from exc


def _normalize_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[: -len("/api/v1")]
    elif path.endswith("/v1"):
        path = path[: -len("/v1")]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
