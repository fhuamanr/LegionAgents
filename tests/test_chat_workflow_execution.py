import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.execution_service import ExecutionService
from core.chat.intent import ChatWorkflowIntentParser
from core.contracts.chat import ChatWorkflowType
from tests.test_real_workflow_runtime import WorkflowModelClient


@pytest.mark.asyncio
async def test_chat_intent_parser_classifies_supported_workflows() -> None:
    parser = ChatWorkflowIntentParser()

    feature = await parser.parse("Build a feature for user onboarding")
    bugfix = await parser.parse("Fix the checkout regression")
    refactor = await parser.parse("Refactor the payment module")
    repo = await parser.parse("Analyze repo https://gitlab.com/example/app.git")

    assert feature.workflow_type == ChatWorkflowType.FEATURE
    assert bugfix.workflow_type == ChatWorkflowType.BUGFIX
    assert refactor.workflow_type == ChatWorkflowType.REFACTOR
    assert repo.workflow_type == ChatWorkflowType.REPOSITORY_ANALYSIS
    assert repo.repository_references == ("https://gitlab.com/example/app.git",)


def test_chat_message_auto_triggers_real_feature_workflow_and_streams_progress() -> None:
    client = TestClient(
        create_app(execution_service=ExecutionService(model_client=WorkflowModelClient()))
    )
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "Feature workflow"},
    ).json()["conversation"]["id"]

    response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Build a feature for workspace execution monitoring."},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["intent"]["workflow_type"] == "feature"
    assert payload["workflow"]["status"] == "completed"

    events = client.get(f"/workspace/chat/conversations/{conversation_id}/events").json()["events"]
    progress_events = [event for event in events if event["type"] == "execution_progress"]
    assert any(event["payload"]["agent_name"] == "ba" for event in progress_events)
    assert any(event["payload"]["event_type"] == "PR_generated" for event in progress_events)


def test_chat_can_resume_workflow_from_conversation_context() -> None:
    client = TestClient(
        create_app(execution_service=ExecutionService(model_client=WorkflowModelClient()))
    )
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "Resume workflow"},
    ).json()["conversation"]["id"]
    first = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Implement a feature for resumable workflows."},
    ).json()

    resume = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Resume the workflow and continue execution.", "resume_workflow": True},
    )

    assert resume.status_code == 201
    assert resume.json()["workflow"]["workflow_id"] == first["workflow"]["workflow_id"]
    assert resume.json()["intent"]["resume_requested"] is True
