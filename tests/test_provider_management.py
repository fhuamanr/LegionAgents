from fastapi.testclient import TestClient

from app.main import create_app
from app.services.execution_service import ExecutionService
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


def test_readiness_reports_provider_state() -> None:
    client = _client()

    response = client.get("/health/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "multi-agent-platform"
    assert payload["checks"]["api"] == "ok"
    assert "llm_provider" in payload["checks"]
