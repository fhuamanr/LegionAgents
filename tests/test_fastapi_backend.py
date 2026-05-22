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
