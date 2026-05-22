from fastapi.testclient import TestClient

from app.main import create_app


def test_healthcheck() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_upload_trigger_status_logs_and_reports() -> None:
    client = TestClient(create_app())

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
    assert workflow["status"] == "running"

    status_response = client.get(f"/executions/{workflow_id}/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["active_agent"] == "ba"

    logs_response = client.get(f"/executions/{workflow_id}/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert any(event["type"] == "agent_started" for event in logs["events"])

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


def test_agent_statuses() -> None:
    client = TestClient(create_app())

    response = client.get("/agents/status")

    assert response.status_code == 200
    assert set(response.json()["agents"]) >= {"ba", "architect", "developer", "qa", "docs", "pr"}


def test_approval_gate_pauses_and_resumes_workflow_api() -> None:
    client = TestClient(create_app())

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
    client = TestClient(create_app())

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
    client = TestClient(create_app())

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
    client = TestClient(create_app())

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
    assert message_response.json()["workflow"]["status"] == "running"

    events_response = client.get(f"/workspace/chat/conversations/{conversation_id}/events")
    assert events_response.status_code == 200
    event_types = {event["type"] for event in events_response.json()["events"]}
    assert {"attachment_uploaded", "workflow_triggered", "execution_progress"} <= event_types
