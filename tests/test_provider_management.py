from fastapi.testclient import TestClient
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from threading import Thread
from uuid import uuid4

from app.main import create_app
from app.schemas import LMStudioLoadModelRequest, ProviderModelAssignRequest, ProviderWorkflowPreflightRequest
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


def test_provider_model_discovery_and_refresh_openai_compatible() -> None:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/v1/models":
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
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        client = _client()
        created = client.post(
            "/providers",
            json={
                "name": "LM Studio",
                "kind": "lm_studio",
                "base_url": base_url,
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
            if self.path == "/v1/models":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"qwen2.5-coder-14b"}]}')
                return
            if self.path == "/api/v0/models/loaded":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"data":[]}')
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            if self.path == "/api/v0/models/load":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"loading"}')
                return
            if self.path == "/api/v0/models/unload":
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
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
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
                ),
            )
        )
        model = next(item for item in response.models if item["model_id"] == "qwen2.5-coder-14b")
        assert model["context_window_tokens"] == 8192
        assert model["runtime_status"] == "loaded"
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
