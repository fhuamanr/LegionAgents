from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.execution_service import ExecutionService
from tests.test_real_workflow_runtime import WorkflowModelClient


def _client() -> TestClient:
    return TestClient(create_app(execution_service=ExecutionService(model_client=WorkflowModelClient())))


def test_agent_playground_ba_run_creates_artifacts_and_handoff() -> None:
    client = _client()
    response = client.post(
        "/agent-playground/run",
        json={
            "agent_name": "ba",
            "input_source": "manual_prompt",
            "prompt": "Necesito un MVP de e-commerce con productos, usuarios y carrito.",
            "local_lm_studio_safe_mode": True,
        },
    )
    assert response.status_code == 200
    artifact = response.json()["artifact"]
    assert artifact["agent_name"] == "ba"
    assert artifact["raw_output"]
    assert "input_tokens" in artifact["token_report"]
    assert "handoff" in artifact


def test_agent_playground_handoff_edit_and_send_to_architect() -> None:
    client = _client()
    ba = client.post(
        "/agent-playground/run",
        json={
            "agent_name": "ba",
            "input_source": "manual_prompt",
            "prompt": "Necesito un MVP de e-commerce con productos, usuarios y carrito.",
            "local_lm_studio_safe_mode": True,
        },
    )
    assert ba.status_code == 200
    artifact = ba.json()["artifact"]
    workflow_id = artifact["workflow_id"]
    execution_id = artifact["execution_id"]
    edited = "NORMALIZED_REQUIREMENT: MVP ecommerce. USER_STORIES: 1. buyer flow"
    update = client.put(
        f"/agent-playground/{workflow_id}/artifacts/{execution_id}/handoff",
        json={"handoff": edited},
    )
    assert update.status_code == 200
    assert update.json()["handoff"] == edited
    architect = client.post(
        "/agent-playground/run",
        json={
            "workflow_id": workflow_id,
            "agent_name": "architect",
            "input_source": "previous_agent_handoff",
            "previous_agent": "ba",
            "prompt": "fallback",
            "local_lm_studio_safe_mode": True,
        },
    )
    assert architect.status_code == 200
    assert architect.json()["artifact"]["agent_name"] == "architect"


def test_agent_playground_workflow_toggles_ba_architect() -> None:
    client = _client()
    response = client.post(
        "/agent-playground/workflow/run",
        json={
            "task": "Build MVP",
            "enabled_agents": ["ba", "architect"],
            "execution_mode": "sequential_auto",
        },
    )
    assert response.status_code == 202
    workflow_id = UUID(response.json()["workflow_id"])
    loaded = client.get(f"/workflows/{workflow_id}")
    assert loaded.status_code == 200
