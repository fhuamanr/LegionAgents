"""LM Studio REST API client for local runtime management."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class LMStudioClient:
    """Thin LM Studio REST client with OpenAI-compatible fallback paths."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds or 30
        self._headers = headers or {}

    def health(self) -> dict[str, Any]:
        payload = self.list_models()
        return {
            "status": "ok",
            "models_count": len(payload.get("data", [])) if isinstance(payload, dict) else 0,
        }

    def list_models(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/models")

    def list_loaded_models(self) -> dict[str, Any]:
        for path in ("/api/v0/models/loaded", "/api/models/loaded", "/api/v1/models/loaded"):
            try:
                return self._request_json("GET", path)
            except Exception:
                continue
        return {"data": []}

    def load_model(self, model: str, *, context_length: int | None = None, max_output_tokens: int | None = None, parallel_slots: int | None = None, gpu_offload: int | None = None, temperature: float | None = None, streaming_enabled: bool | None = None) -> dict[str, Any]:
        body = {
            "model": model,
            "identifier": model,
            "context_length": context_length,
            "n_ctx": context_length,
            "max_output_tokens": max_output_tokens,
            "n_parallel": parallel_slots,
            "parallel_slots": parallel_slots,
            "gpu_offload": gpu_offload,
            "temperature": temperature,
            "streaming_enabled": streaming_enabled,
        }
        body = {key: value for key, value in body.items() if value is not None}
        for path in ("/api/v0/models/load", "/api/models/load", "/api/v1/models/load"):
            try:
                return self._request_json("POST", path, body=body)
            except Exception:
                continue
        raise ValueError("LM Studio load model endpoint is not available.")

    def unload_model(self, model: str) -> dict[str, Any]:
        body = {"model": model, "identifier": model}
        for path in ("/api/v0/models/unload", "/api/models/unload", "/api/v1/models/unload"):
            try:
                return self._request_json("POST", path, body=body)
            except Exception:
                continue
        raise ValueError("LM Studio unload model endpoint is not available.")

    def download_model(self, model: str) -> dict[str, Any]:
        body = {"model": model, "identifier": model}
        for path in ("/api/v0/models/download", "/api/models/download", "/api/v1/models/download"):
            try:
                return self._request_json("POST", path, body=body)
            except Exception:
                continue
        raise ValueError("LM Studio download endpoint is not available.")

    def download_status(self, download_id: str | None = None, model: str | None = None) -> dict[str, Any]:
        query = ""
        if download_id:
            query = f"?download_id={download_id}"
        elif model:
            query = f"?model={model}"
        for path in ("/api/v0/models/downloads", "/api/models/downloads", "/api/v1/models/downloads"):
            try:
                return self._request_json("GET", f"{path}{query}")
            except Exception:
                continue
        return {"data": []}

    def chat_completion(self, *, model: str, messages: list[dict[str, str]], stream: bool = False, max_tokens: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        return self._request_json("POST", "/v1/chat/completions", body=body)

    def _request_json(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        request_body = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json", **self._headers}
        if request_body is not None:
            headers["Content-Type"] = "application/json"
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(url, data=request_body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = response.read().decode("utf-8") or "{}"
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"LM Studio request failed: {exc.code} {body_text or exc.reason}") from exc
