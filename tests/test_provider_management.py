from fastapi.testclient import TestClient
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from threading import Thread
from uuid import uuid4

from app.main import create_app
from app.schemas import LMStudioLoadModelRequest, ProviderModelAssignRequest, ProviderUpsertApiRequest, ProviderWorkflowPreflightRequest
from app.services.provider_service import ProviderApplicationService
from app.services.execution_service import ExecutionService
from core.agents.providers import ProviderConfig, ProviderKind, ProviderRegistry
from tests.test_real_workflow_runtime import WorkflowModelClient


def _client() -> TestClient:
    return TestClient(create_app(execution_service=ExecutionService(model_client=WorkflowModelClient())))


def test_provider_management_api_persists_and_masks_keys() -> None:
    client = _client()

    created = client.post(
        "/providers",
        json={
            "name": "OpenRouter",
            "kind": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-test-provider-key",
            "default_model": "openai/gpt-4o-mini",
            "agent_models": {"developer": "anthropic/claude-3.5-sonnet"},
        },
    )

    assert created.status_code == 201
    provider = created.json()["provider"]
    assert provider["api_key"] == "sk-t...-key"
    assert provider["configured"] is True
    assert provider["agent_models"]["developer"] == "anthropic/claude-3.5-sonnet"

    provider_id = provider["id"]
    listed = client.get("/providers")
    assert listed.status_code == 200
    assert any(item["id"] == provider_id for item in listed.json()["providers"])

    health = client.get(f"/providers/{provider_id}/health")
    assert health.status_code == 200
    assert health.json()["checks"][0]["status"] == "ok"


def test_provider_management_api_flags_incomplete_custom_provider() -> None:
    client = _client()

    created = client.post(
        "/providers",
        json={
            "name": "Custom endpoint",
            "kind": "custom",
            "default_model": "local-model",
        },
    )

    assert created.status_code == 201
    provider_id = created.json()["provider"]["id"]
    health = client.get(f"/providers/{provider_id}/health")

    assert health.status_code == 200
    assert health.json()["checks"][0]["status"] == "warning"


def test_provider_update_and_delete_prevent_duplicate_names() -> None:
    client = _client()
    create_first = client.post(
        "/providers",
        json={
            "name": "OpenAI Primary",
            "kind": "openai",
            "api_key": "sk-first-key",
            "default_model": "gpt-5-mini",
        },
    )
    assert create_first.status_code == 201
    provider_id = create_first.json()["provider"]["id"]

    create_second = client.post(
        "/providers",
        json={
            "name": "OpenAI Primary",
            "kind": "openai",
            "api_key": "sk-updated-key",
            "default_model": "gpt-5",
        },
    )
    assert create_second.status_code == 201
    assert create_second.json()["provider"]["id"] == provider_id

    listed = client.get("/providers").json()["providers"]
    assert len([provider for provider in listed if provider["name"] == "OpenAI Primary"]) == 1

    deleted = client.delete(f"/providers/{provider_id}")
    assert deleted.status_code == 204


def test_default_provider_persists_when_set() -> None:
    client = _client()
    created = client.post(
        "/providers",
        json={
            "name": "Default Provider",
            "kind": "openai",
            "api_key": "sk-default-provider",
            "default_model": "gpt-5-mini",
            "is_default": True,
        },
    )
    assert created.status_code == 201
    provider = created.json()["provider"]
    assert provider["is_default"] is True

    listed = client.get("/providers")
    assert listed.status_code == 200
    providers = listed.json()["providers"]
    same = next(item for item in providers if item["id"] == provider["id"])
    assert same["is_default"] is True


def test_readiness_reports_provider_state() -> None:
    client = _client()

    response = client.get("/health/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "multi-agent-platform"
    assert payload["checks"]["api"] == "ok"
    assert "llm_provider" in payload["checks"]


def test_provider_connectivity_endpoint() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/v1/models":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{\"data\": []}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        client = _client()
        response = client.post(
            "/providers/test-connection",
            json={
                "name": "Local test",
                "kind": "custom",
                "base_url": base_url,
                "default_model": "test-model",
            },
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert payload["status"] == "success"
        assert payload["latency_ms"] >= 0
        assert payload["capabilities"]["supports_text_response_format"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_provider_connectivity_local_lm_studio_payload_contract_and_normalization() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"models":[{"key":"qwen2.5-coder-14b-instruct"}]}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}/api/v1"
        client = _client()
        response = client.post(
            "/providers/test-connection",
            json={
                "name": "Local LM Studio",
                "kind": "local_lm_studio",
                "base_url": base_url,
                "api_key": "lm-token",
                "default_model": "qwen2.5-coder-14b-instruct",
                "context_window_tokens": 8820,
                "reserved_output_tokens": 1024,
                "max_prompt_tokens": 3000,
                "management_base_url": f"http://127.0.0.1:{server.server_port}",
                "inference_base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "lm_studio_auth_mode": "raw",
            },
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert payload["status"] in {"success", "warning"}
    finally:
        server.shutdown()
        server.server_close()


def test_provider_save_normalizes_local_lm_studio_base_url() -> None:
    client = _client()
    created = client.post(
        "/providers",
        json={
            "name": "Local LM Studio",
            "kind": "local_lm_studio",
            "base_url": "http://127.0.0.1:1234/api/v1",
            "default_model": "local-model",
            "metadata": {"lm_studio_auth_mode": "raw"},
        },
    )
    assert created.status_code == 201
    provider = created.json()["provider"]
    assert provider["base_url"] == "http://127.0.0.1:1234/v1"
    assert provider["metadata"]["management_base_url"] == "http://127.0.0.1:1234"
    assert provider["metadata"]["inference_base_url"] == "http://127.0.0.1:1234/v1"


def test_refresh_models_deleted_provider_returns_404() -> None:
    client = _client()
    created = client.post(
        "/providers",
        json={
            "name": "ToDelete",
            "kind": "local_lm_studio",
            "base_url": "http://127.0.0.1:1234",
            "default_model": "local-model",
        },
    )
    assert created.status_code == 201
    provider_id = created.json()["provider"]["id"]
    deleted = client.delete(f"/providers/{provider_id}")
    assert deleted.status_code == 204
    refreshed = client.post(f"/providers/{provider_id}/models/refresh")
    assert refreshed.status_code == 404


def test_provider_model_discovery_and_refresh_openai_compatible() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                auth = self.headers.get("Authorization", "")
                if auth != "lm-token":
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"local-small"},{"id":"local-large"}]}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        client = _client()
        created = client.post(
            "/providers",
            json={
                "name": "LM Studio",
                "kind": "lm_studio",
                "base_url": base_url,
                "api_key": "lm-token",
                "default_model": "local-small",
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["provider"]["id"]
        refreshed = client.post(f"/providers/{provider_id}/models/refresh")
        assert refreshed.status_code == 200
        models = refreshed.json()["models"]
        assert len(models) == 2
        assert {item["model_id"] for item in models} == {"local-small", "local-large"}
    finally:
        server.shutdown()
        server.server_close()


def test_lmstudio_model_discovery_supports_models_key_shape() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                auth = self.headers.get("Authorization", "")
                if auth != "lm-token":
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'{"models":[{"id":"qwen2.5-coder-14b-instruct","object":"model","owned_by":"lmstudio"},'
                    b'{"id":"mistralai/devstral-small-2-2512","object":"model","owned_by":"lmstudio"}]}'
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        client = _client()
        created = client.post(
            "/providers",
            json={
                "name": "LM Studio",
                "kind": "lm_studio",
                "base_url": base_url,
                "api_key": "lm-token",
                "default_model": "local-model",
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["provider"]["id"]
        refreshed = client.post(f"/providers/{provider_id}/models/refresh")
        assert refreshed.status_code == 200
        models = refreshed.json()["models"]
        assert len(models) == 2
        ids = {item["model_id"] for item in models}
        assert "qwen2.5-coder-14b-instruct" in ids
        assert "mistralai/devstral-small-2-2512" in ids
        assert "local-model" not in ids
    finally:
        server.shutdown()
        server.server_close()


def test_lmstudio_model_discovery_supports_root_list_and_alt_id_fields() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                auth = self.headers.get("Authorization", "")
                if auth != "lm-token":
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'[{"model":"qwen3-coder-30b-a3b-instruct"},'
                    b'{"model_id":"google/gemma-4-e4b"},'
                    b'{"name":"liquid/lfm2.5-1.2b"}]'
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        client = _client()
        created = client.post(
            "/providers",
            json={
                "name": "LM Studio Alt",
                "kind": "lm_studio",
                "base_url": base_url,
                "api_key": "lm-token",
                "default_model": "local-model",
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["provider"]["id"]
        refreshed = client.post(f"/providers/{provider_id}/models/refresh")
        assert refreshed.status_code == 200
        models = refreshed.json()["models"]
        ids = {item["model_id"] for item in models}
        assert "qwen3-coder-30b-a3b-instruct" in ids
        assert "google/gemma-4-e4b" in ids
        assert "liquid/lfm2.5-1.2b" in ids
    finally:
        server.shutdown()
        server.server_close()


def test_provider_model_discovery_ollama_tags() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/tags":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"models":[{"name":"llama3.1:8b","details":{"family":"llama"}},{"name":"qwen2.5:7b"}]}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        client = _client()
        created = client.post(
            "/providers",
            json={
                "name": "Ollama Local",
                "kind": "ollama",
                "base_url": base_url,
                "default_model": "llama3.1:8b",
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["provider"]["id"]
        refreshed = client.post(f"/providers/{provider_id}/models/refresh")
        assert refreshed.status_code == 200
        models = refreshed.json()["models"]
        assert len(models) >= 1
        assert any(item["model_id"] == "llama3.1:8b" for item in models)
    finally:
        server.shutdown()
        server.server_close()


def test_provider_manual_model_profile_update() -> None:
    client = _client()
    created = client.post(
        "/providers",
        json={
            "name": "Manual Custom",
            "kind": "custom",
            "base_url": "http://example.local/v1",
            "default_model": "my-model",
        },
    )
    assert created.status_code == 201
    provider_id = created.json()["provider"]["id"]
    updated = client.put(
        f"/providers/{provider_id}/models/my-model",
        json={
            "context_window_tokens": 16384,
            "max_input_tokens": 12000,
            "max_output_tokens": 2000,
            "compact_mode_required": False,
            "supports_json_mode": True,
            "notes": "manual profile",
        },
    )
    assert updated.status_code == 200
    models = updated.json()["models"]
    model = next(item for item in models if item["model_id"] == "my-model")
    assert model["context_window_tokens"] == 16384
    assert model["detection_source"] == "manual"


def test_lmstudio_runtime_management_updates_actual_context_profile() -> None:
    import asyncio

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                auth = self.headers.get("Authorization", "")
                if auth != "lm-token":
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"qwen2.5-coder-14b"}]}')
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            auth = self.headers.get("Authorization", "")
            if auth != "lm-token":
                self.send_response(401)
                self.end_headers()
                return
            if self.path == "/api/v1/models/load":
                body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")).decode("utf-8")
                assert '"model": "qwen2.5-coder-14b"' in body
                assert '"context_length": 8192' in body
                assert '"flash_attention": true' in body
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"loaded","instance_id":"qwen2.5-coder-14b"}')
                return
            if self.path == "/api/v1/models/unload":
                body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")).decode("utf-8")
                assert '"instance_id": "qwen2.5-coder-14b"' in body
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"unloaded"}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        registry = ProviderRegistry()
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url=f"http://127.0.0.1:{server.server_port}",
            api_key="lm-token",
            default_model="qwen2.5-coder-14b",
        )
        asyncio.run(registry.upsert(provider))
        response = asyncio.run(
            service.lmstudio_load_model(
                provider.id,
                LMStudioLoadModelRequest(
                    model_id="qwen2.5-coder-14b",
                    context_length=8192,
                    parallel_slots=1,
                    flash_attention=True,
                ),
            )
        )
        model = next(item for item in response.models if item["model_id"] == "qwen2.5-coder-14b")
        assert model["context_window_tokens"] == 8192
        assert model["runtime_status"] == "loaded"
        unloaded = asyncio.run(service.lmstudio_unload_model(provider.id, model_id="qwen2.5-coder-14b"))
        model2 = next(item for item in unloaded.models if item["model_id"] == "qwen2.5-coder-14b")
        assert model2["runtime_status"] == "unloaded"
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous
        server.shutdown()
        server.server_close()


def test_provider_preflight_warns_unloaded_local_models() -> None:
    registry = ProviderRegistry()
    service = ProviderApplicationService(registry)
    import asyncio

    provider = ProviderConfig(
        id=uuid4(),
        name="LM Studio",
        kind=ProviderKind.LM_STUDIO,
        base_url="http://localhost:1234/v1",
        default_model="qwen",
        agent_models={"ba": "qwen"},
    )
    asyncio.run(registry.upsert(provider))
    asyncio.run(registry.update_model_profile(provider.id, "qwen", {"runtime_status": "unloaded", "context_window_tokens": 4096}))
    result = asyncio.run(service.preflight(provider.id, ProviderWorkflowPreflightRequest(required_agents=("ba",))))
    assert result.ok is False
    assert any("not loaded" in warning for warning in result.warnings)


def test_assign_agent_model_updates_provider_mapping() -> None:
    registry = ProviderRegistry()
    service = ProviderApplicationService(registry)
    import asyncio

    provider = ProviderConfig(
        id=uuid4(),
        name="Local",
        kind=ProviderKind.LOCAL_LM_STUDIO,
        base_url="http://localhost:1234/v1",
        default_model="model-a",
    )
    asyncio.run(registry.upsert(provider))
    updated = asyncio.run(service.assign_agent_model(provider.id, agent_name="architect", request=ProviderModelAssignRequest(model_id="model-b")))
    assert updated.provider["agent_models"]["architect"] == "model-b"


def test_lmstudio_missing_token_blocks_before_call() -> None:
    import asyncio

    registry = ProviderRegistry()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url="http://localhost:1234",
            default_model="qwen",
        )
        asyncio.run(registry.upsert(provider))
        try:
            asyncio.run(service.lmstudio_runtime_models(provider.id))
            assert False, "expected token missing error"
        except ValueError as exc:
            assert "lm_studio_token_missing" in str(exc)
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous


def test_lmstudio_401_maps_to_token_rejected() -> None:
    import asyncio

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"unauthorized"}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        registry = ProviderRegistry()
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url=f"http://127.0.0.1:{server.server_port}",
            api_key="bad-token",
            default_model="qwen",
        )
        asyncio.run(registry.upsert(provider))
        try:
            asyncio.run(service.lmstudio_runtime_models(provider.id))
            assert False, "expected token rejection"
        except ValueError as exc:
            assert "lm_studio_token_rejected" in str(exc)
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous
        server.shutdown()
        server.server_close()


def test_lmstudio_download_and_status_use_v1_endpoints_with_bearer() -> None:
    import asyncio

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path == "/api/v1/models/download":
                assert self.headers.get("Authorization") == "lm-token"
                body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")).decode("utf-8")
                assert '"model": "qwen2.5-coder-14b"' in body
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"downloading"}')
                return
            self.send_response(404)
            self.end_headers()

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/api/v1/models/download/status"):
                assert self.headers.get("Authorization") == "lm-token"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        registry = ProviderRegistry()
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url=f"http://127.0.0.1:{server.server_port}",
            api_key="lm-token",
            default_model="qwen2.5-coder-14b",
        )
        asyncio.run(registry.upsert(provider))
        download = asyncio.run(service.lmstudio_download_model(provider.id, model_id="qwen2.5-coder-14b"))
        assert download.result["status"] == "downloading"
        status = asyncio.run(service.lmstudio_download_status(provider.id, model="qwen2.5-coder-14b"))
        assert status.result["status"] == "ok"
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous
        server.shutdown()
        server.server_close()


def test_lmstudio_discovery_maps_v1_models_key_shape() -> None:
    import asyncio

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                assert self.headers.get("Authorization") == "lm-token"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'{"models":[{"type":"llm","publisher":"lmstudio-community","key":"qwen2.5-coder-14b-instruct","display_name":"Qwen2.5 Coder 14B Instruct","max_context_length":32768,"loaded_instances":[]},{"type":"llm","publisher":"google","key":"google/gemma-4-e4b","display_name":"Gemma 4 E4B","max_context_length":131072,"loaded_instances":[{"id":"google/gemma-4-e4b"}]}]}'
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        registry = ProviderRegistry()
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url=f"http://127.0.0.1:{server.server_port}",
            api_key="lm-token",
            default_model="local-model",
        )
        asyncio.run(registry.upsert(provider))
        refreshed = asyncio.run(service.refresh_models(provider.id))
        model_ids = {item["model_id"] for item in refreshed.models}
        assert "qwen2.5-coder-14b-instruct" in model_ids
        assert "google/gemma-4-e4b" in model_ids
        qwen = next(item for item in refreshed.models if item["model_id"] == "qwen2.5-coder-14b-instruct")
        assert qwen["context_window_tokens"] == 32768
        gemma = next(item for item in refreshed.models if item["model_id"] == "google/gemma-4-e4b")
        assert gemma["runtime_status"] == "loaded"
    finally:
        server.shutdown()
        server.server_close()


def test_lmstudio_bearer_auth_mode_for_management_endpoints() -> None:
    import asyncio

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/v1/models":
                assert self.headers.get("Authorization") == "Bearer lm-token"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"models":[{"key":"qwen2.5-coder-14b-instruct"}]}')
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            if self.path == "/api/v1/models/load":
                assert self.headers.get("Authorization") == "Bearer lm-token"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"loaded","instance_id":"qwen2.5-coder-14b-instruct"}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        registry = ProviderRegistry()
        service = ProviderApplicationService(registry)
        provider = ProviderConfig(
            id=uuid4(),
            name="LM Studio",
            kind=ProviderKind.LM_STUDIO,
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key="lm-token",
            default_model="qwen2.5-coder-14b-instruct",
            metadata={"lm_studio_auth_mode": "bearer"},
        )
        asyncio.run(registry.upsert(provider))
        models = asyncio.run(service.refresh_models(provider.id))
        assert any(item["model_id"] == "qwen2.5-coder-14b-instruct" for item in models.models)
        loaded = asyncio.run(
            service.lmstudio_load_model(
                provider.id,
                LMStudioLoadModelRequest(
                    model_id="qwen2.5-coder-14b-instruct",
                    context_length=8820,
                    flash_attention=True,
                    echo_load_config=True,
                ),
            )
        )
        assert any(item["runtime_status"] == "loaded" for item in loaded.models)
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous
        server.shutdown()
        server.server_close()


def test_provider_update_does_not_overwrite_token_with_masked_placeholder() -> None:
    import asyncio

    registry = ProviderRegistry()
    service = ProviderApplicationService(registry)
    provider = ProviderConfig(
        id=uuid4(),
        name="LM Studio",
        kind=ProviderKind.LM_STUDIO,
        base_url="http://localhost:1234/v1",
        api_key="real-secret-token",
        default_model="qwen2.5-coder-14b-instruct",
    )
    asyncio.run(registry.upsert(provider))
    updated = asyncio.run(
        service.save(
            ProviderUpsertApiRequest(
                name="LM Studio",
                kind="lm_studio",
                base_url="http://localhost:1234/v1",
                api_key="sk-l...Ox01",
                default_model="qwen2.5-coder-14b-instruct",
                status="active",
            ),
            provider.id,
        )
    )
    assert updated.provider["api_key"] == "real...oken"


def test_runtime_model_routes_allow_local_trusted_mode_without_auth_principal() -> None:
    client = _client()
    previous = os.environ.get("ENABLE_LOCAL_MODEL_MANAGEMENT")
    os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = "true"
    try:
        created = client.post(
            "/providers",
            json={
                "name": "LM Studio",
                "kind": "lm_studio",
                "base_url": "http://localhost:1234/v1",
                "default_model": "qwen2.5-coder-14b-instruct",
                "status": "active",
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["provider"]["id"]
        response = client.post(
            f"/providers/{provider_id}/runtime-models/load",
            json={"model_id": "qwen2.5-coder-14b-instruct", "context_length": 8820, "flash_attention": True, "echo_load_config": True},
        )
        assert response.status_code != 401
    finally:
        if previous is None:
            os.environ.pop("ENABLE_LOCAL_MODEL_MANAGEMENT", None)
        else:
            os.environ["ENABLE_LOCAL_MODEL_MANAGEMENT"] = previous
