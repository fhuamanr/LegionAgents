from fastapi.testclient import TestClient
import time

from app.services.execution_service import ExecutionService
from app.main import create_app
from tests.test_real_workflow_runtime import WorkflowModelClient
from core.agents.runtime import AgentModelClient
from core.contracts.prompts import PromptMessage


def _client() -> TestClient:
    return TestClient(create_app(execution_service=ExecutionService(model_client=WorkflowModelClient())))


def _client_without_provider() -> TestClient:
    return TestClient(create_app(execution_service=ExecutionService()))


class ChatStreamingModelClient(AgentModelClient):
    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        user = next((message.content for message in messages if message.role.value == "user"), "")
        return f"Echo: {user}"

    async def stream_complete(self, messages: tuple[PromptMessage, ...]):
        yield "Echo: "
        user = next((message.content for message in messages if message.role.value == "user"), "")
        yield user


def _client_with_chat_streaming() -> TestClient:
    return TestClient(create_app(execution_service=ExecutionService(model_client=ChatStreamingModelClient())))


def test_healthcheck() -> None:
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_upload_trigger_status_logs_and_reports() -> None:
    client = _client()

    upload_response = client.post(
        "/uploads/user-stories",
        json={
            "title": "Login story",
            "content": "As a user, I can log in.",
            "metadata": {"source": "test"},
        },
    )
    assert upload_response.status_code == 201
    upload_id = upload_response.json()["upload_id"]

    workflow_response = client.post(
        "/workflows",
        json={
            "task": "Deliver login feature",
            "upload_id": upload_id,
            "thread_id": "thread-1",
        },
    )
    assert workflow_response.status_code == 202
    workflow = workflow_response.json()
    workflow_id = workflow["workflow_id"]
    assert workflow["status"] == "completed"
    assert workflow["metadata"]["execution_id"]
    assert workflow["metadata"]["checkpoint_count"] >= 6

    status_response = client.get(f"/executions/{workflow_id}/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["active_agent"] == "pr"
    assert status["progress_percent"] == 100.0

    logs_response = client.get(f"/executions/{workflow_id}/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert any(event["type"] == "agent_started" for event in logs["events"])
    assert any(event["type"] == "PR_generated" for event in logs["events"])

    telemetry_response = client.get(f"/executions/{workflow_id}/telemetry")
    assert telemetry_response.status_code == 200
    telemetry = telemetry_response.json()
    assert telemetry["workflow_id"] == workflow_id
    assert {node["id"] for node in telemetry["nodes"]} >= {"ba", "architect", "developer", "qa", "docs", "pr"}
    assert any(edge["is_loop"] for edge in telemetry["edges"])
    assert "QA -->|rejected retry| Developer" in telemetry["mermaid"]
    assert telemetry["metadata"]["websocket_channel"] == f"/ws/executions/{workflow_id}"

    qa_response = client.get(f"/reports/qa/{workflow_id}")
    docs_response = client.get(f"/docs/generated/{workflow_id}")
    pr_response = client.get(f"/pr/summaries/{workflow_id}")
    assert qa_response.json()["kind"] == "qa_report"
    assert docs_response.json()["kind"] == "generated_documentation"
    assert pr_response.json()["kind"] == "pr_summary"
    artifacts_response = client.get(f"/workflows/{workflow_id}/artifacts")
    assert artifacts_response.status_code == 200
    files = artifacts_response.json()["files"]
    assert any(item["relative_path"].startswith("ba/") for item in files)
    assert any(item["relative_path"].startswith("architect/") for item in files)
    assert any(item["relative_path"].startswith("developer/") for item in files)
    assert any(item["relative_path"].startswith("docs/") for item in files)
    assert any(item["relative_path"] == "docs/raw_output.md" for item in files)


def test_agent_statuses() -> None:
    client = _client()

    response = client.get("/agents/status")

    assert response.status_code == 200
    assert set(response.json()["agents"]) >= {"ba", "architect", "developer", "qa", "docs", "pr"}


def test_improve_existing_execution_generates_quality_bundle() -> None:
    client = _client()
    workflow_response = client.post("/workflows", json={"task": "Deliver quality bundle"})
    assert workflow_response.status_code == 202
    workflow = workflow_response.json()
    workflow_id = workflow["workflow_id"]
    artifact_root = workflow["metadata"]["artifacts_root"]

    improve_response = client.post(
        f"/workflows/{workflow_id}/improve",
        json={
            "artifact_root": artifact_root,
            "selected_agents": ["ba", "architect", "developer", "qa", "docs"],
            "improvement_depth": "balanced",
        },
    )
    assert improve_response.status_code == 200
    payload = improve_response.json()
    assert payload["workflow_id"] == workflow_id
    assert payload["quality_report_path"].endswith("quality_report.md")
    assert "implementation_depth" in payload["quality_metrics"]


def test_approval_gate_pauses_and_resumes_workflow_api() -> None:
    client = _client()

    workflow_response = client.post(
        "/workflows",
        json={"task": "Deliver approval gated feature", "thread_id": "thread-approval"},
    )
    workflow_id = workflow_response.json()["workflow_id"]

    approval_response = client.post(
        "/approvals",
        json={
            "workflow_id": workflow_id,
            "gate_type": "qa_override",
            "title": "Approve QA override",
            "description": "Allow workflow to continue after QA rejection.",
            "requested_by": "qa",
            "required_reviewers": [
                {"reviewer_id": "lead-1", "display_name": "Delivery Lead", "role": "lead"}
            ],
            "pause_reason": "qa_override_required",
        },
    )

    assert approval_response.status_code == 201
    approval = approval_response.json()
    assert approval["status"] == "pending"

    paused_workflow = client.get(f"/workflows/{workflow_id}").json()
    assert paused_workflow["status"] == "paused"
    assert paused_workflow["metadata"]["approval_id"] == approval["approval_id"]

    pause_response = client.get(f"/approvals/workflows/{workflow_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["reason"] == "qa_override_required"

    decision_response = client.post(
        f"/approvals/{approval['approval_id']}/decisions",
        json={
            "decision": "approve",
            "reviewer": {"reviewer_id": "lead-1", "display_name": "Delivery Lead"},
            "reason": "Override approved.",
        },
    )

    assert decision_response.status_code == 200
    decision = decision_response.json()
    assert decision["can_resume"] is True
    assert decision["route_signal"] == "qa_override_approved"

    resumed_workflow = client.get(f"/workflows/{workflow_id}").json()
    assert resumed_workflow["status"] == "running"


def test_observability_api_exposes_metrics_and_analytics() -> None:
    client = _client()

    workflow_response = client.post(
        "/workflows",
        json={"task": "Deliver observable workflow", "thread_id": "thread-observe"},
    )
    workflow_id = workflow_response.json()["workflow_id"]

    snapshot_response = client.get("/observability/snapshot")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()["snapshot"]
    assert snapshot["metadata"]["prometheus_ready"] is True
    assert snapshot["metadata"]["opentelemetry_ready"] is True

    workflow_analytics_response = client.get(f"/observability/workflows/{workflow_id}")
    assert workflow_analytics_response.status_code == 200
    assert workflow_analytics_response.json()["workflow_id"] == workflow_id

    agents_response = client.get("/observability/agents")
    assert agents_response.status_code == 200
    assert any(agent["agent_name"] == "ba" for agent in agents_response.json()["agents"])

    prometheus_response = client.get("/observability/metrics/prometheus")
    assert prometheus_response.status_code == 200
    assert "execution_events_total" in prometheus_response.text

    grafana_response = client.get("/observability/exporters/grafana")
    assert grafana_response.status_code == 200
    assert grafana_response.json()["title"] == "Multi-Agent Delivery Observability"


def test_governance_management_api_supports_versions_and_rollback() -> None:
    client = _client()

    first = client.post(
        "/governance/configs",
        json={
            "scope": "global",
            "kind": "gravity",
            "name": "Global Gravity",
            "markdown": "- Always preserve modularity.",
            "updated_by": "admin",
            "change_summary": "Initial governance rule.",
        },
    )
    assert first.status_code == 201
    document_id = first.json()["document"]["id"]

    second = client.post(
        "/governance/configs",
        json={
            "scope": "global",
            "kind": "gravity",
            "name": "Global Gravity",
            "markdown": "- Always preserve modularity.\n- Always keep prompts modular.",
            "updated_by": "admin",
            "change_summary": "Added prompt rule.",
        },
    )
    assert second.status_code == 201
    assert second.json()["document"]["version"] >= 2

    versions = client.get(f"/governance/configs/{document_id}/versions")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) >= 2

    rollback = client.post(
        f"/governance/configs/{document_id}/rollback",
        json={"target_version": 1, "updated_by": "admin"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["document"]["markdown"] == "- Always preserve modularity."

    reloads = client.get("/governance/configs/reloads")
    assert reloads.status_code == 200
    assert len(reloads.json()["events"]) >= 3


def test_workspace_chat_api_uploads_references_and_triggers_workflow() -> None:
    client = _client()

    conversation_response = client.post(
        "/workspace/chat/conversations",
        json={"title": "Chat delivery workspace", "created_by": "tester"},
    )
    assert conversation_response.status_code == 201
    conversation_id = conversation_response.json()["conversation"]["id"]

    attachment_response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/attachments",
        json={
            "kind": "markdown",
            "name": "story.md",
            "content": "# Story\nAs a user, I can trigger workflows from chat.",
            "content_type": "text/markdown",
        },
    )
    assert attachment_response.status_code == 201
    attachment_id = attachment_response.json()["attachment"]["id"]

    git_response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/attachments",
        json={
            "kind": "git_repository",
            "name": "platform repo",
            "uri": "https://gitlab.com/example/platform.git",
        },
    )
    assert git_response.status_code == 201

    message_response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={
            "content": "Trigger implementation workflow.",
            "attachment_ids": [attachment_id],
            "trigger_workflow": True,
        },
    )
    assert message_response.status_code == 201
    workflow_id = message_response.json()["workflow"]["workflow_id"]
    deadline = time.time() + 10
    final_status = ""
    while time.time() < deadline:
        status_payload = client.get(f"/executions/{workflow_id}/status").json()
        final_status = status_payload["status"]
        if final_status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.1)
    assert final_status in {"running", "completed"}

    events_response = client.get(f"/workspace/chat/conversations/{conversation_id}/events")
    assert events_response.status_code == 200
    event_types = {event["type"] for event in events_response.json()["events"]}
    assert {"attachment_uploaded", "workflow_triggered", "execution_progress"} <= event_types


def test_workspace_chat_send_persists_assistant_error_when_no_provider() -> None:
    client = _client_without_provider()
    conversation_response = client.post(
        "/workspace/chat/conversations",
        json={"title": "No provider chat", "created_by": "tester"},
    )
    assert conversation_response.status_code == 201
    conversation_id = conversation_response.json()["conversation"]["id"]

    message_response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Hello, explain this platform", "trigger_workflow": False},
    )
    assert message_response.status_code == 201

    deadline = time.time() + 3
    assistant = None
    while time.time() < deadline:
        conversation = client.get(f"/workspace/chat/conversations/{conversation_id}").json()["conversation"]
        if len(conversation["messages"]) >= 2 and conversation["messages"][-1]["role"] == "assistant":
            assistant = conversation["messages"][-1]
            if assistant.get("status") in {"failed", "completed"}:
                break
        time.sleep(0.1)
    assert assistant is not None
    assert assistant["status"] == "failed"
    assert "Provider error:" in assistant["error"]


def test_workspace_chat_delete_conversation() -> None:
    client = _client()
    conversation_response = client.post(
        "/workspace/chat/conversations",
        json={"title": "Delete me", "created_by": "tester"},
    )
    conversation_id = conversation_response.json()["conversation"]["id"]
    deleted = client.delete(f"/workspace/chat/conversations/{conversation_id}")
    assert deleted.status_code == 204
    listed = client.get("/workspace/chat/conversations").json()["conversations"]
    assert all(item["id"] != conversation_id for item in listed)


def test_workspace_chat_workflow_run_does_not_duplicate_user_message() -> None:
    client = _client()
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "Workflow no duplicate", "created_by": "tester"},
    ).json()["conversation"]["id"]
    send = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Run workflow once", "trigger_workflow": True},
    )
    assert send.status_code == 201
    conversation = client.get(f"/workspace/chat/conversations/{conversation_id}").json()["conversation"]
    user_messages = [message for message in conversation["messages"] if message["role"] == "user"]
    assert len(user_messages) == 1


def test_workspace_chat_send_returns_immediately_with_pending_assistant() -> None:
    client = _client()
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "Async chat", "created_by": "tester"},
    ).json()["conversation"]["id"]
    response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "Hello async chat", "trigger_workflow": False},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["job_id"] is not None
    assert payload["assistant_message"] is not None
    assert payload["assistant_message"]["status"] in {"pending", "streaming", "completed"}


def test_workspace_chat_streaming_completes_and_persists() -> None:
    client = _client_with_chat_streaming()
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "Streaming chat", "created_by": "tester"},
    ).json()["conversation"]["id"]
    response = client.post(
        f"/workspace/chat/conversations/{conversation_id}/messages",
        json={"content": "hola, quien eres", "trigger_workflow": False},
    )
    assert response.status_code == 201
    deadline = time.time() + 5
    completed = None
    while time.time() < deadline:
        conversation = client.get(f"/workspace/chat/conversations/{conversation_id}").json()["conversation"]
        assistant = [message for message in conversation["messages"] if message["role"] == "assistant"][-1]
        if assistant.get("status") == "completed":
            completed = assistant
            break
        time.sleep(0.1)
    assert completed is not None
    assert completed["content"] == "Echo: hola, quien eres"
    events = client.get(f"/workspace/chat/conversations/{conversation_id}/events").json()["events"]
    completion_events = [
        event for event in events
        if event["type"] == "execution_progress"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("id") == completed["id"]
        and event["payload"].get("status") == "completed"
    ]
    assert completion_events
    assert completion_events[-1]["payload"]["content"] == "Echo: hola, quien eres"


def test_workspace_chat_sse_stream_emits_started_delta_and_completed() -> None:
    client = _client_with_chat_streaming()
    conversation_id = client.post(
        "/workspace/chat/conversations",
        json={"title": "SSE chat", "created_by": "tester"},
    ).json()["conversation"]["id"]
    with client.stream(
        "POST",
        f"/workspace/chat/conversations/{conversation_id}/messages/stream",
        json={"content": "hola, quien eres", "trigger_workflow": False},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: message_started" in body
    assert "event: content_delta" in body
    assert "event: message_completed" in body
    conversation = client.get(f"/workspace/chat/conversations/{conversation_id}").json()["conversation"]
    assistant = [message for message in conversation["messages"] if message["role"] == "assistant"][-1]
    assert assistant["status"] == "completed"
    assert assistant["content"] == "Echo: hola, quien eres"


def test_governance_seed_loads_repository_markdown_documents() -> None:
    client = _client()
    first = client.get("/governance/configs")
    second = client.get("/governance/configs")
    assert first.status_code == 200
    assert second.status_code == 200
    first_docs = first.json()["documents"]
    second_docs = second.json()["documents"]
    assert len(first_docs) > 10
    assert len(second_docs) == len(first_docs)
    assert any(doc["kind"] == "anti_gravity" for doc in first_docs)
    assert any((doc.get("source_type") == "seeded_file") or (doc.get("metadata", {}).get("source_type") == "seeded_file") for doc in first_docs)


def test_upload_files_api_supports_multiple_files() -> None:
    client = _client()
    response = client.post(
        "/uploads/files",
        files=[
            ("files", ("story.md", b"# Story\nAs a user...", "text/markdown")),
            ("files", ("requirements.txt", b"As a user I can upload.", "text/plain")),
        ],
    )
    assert response.status_code == 201
    payload = response.json()
    assert len(payload) == 2
