import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.contracts.security import (
    AccessCheckRequest,
    AuditEvent,
    AuditEventType,
    AuditQuery,
    SecurityPermission,
    SecurityRole,
    TokenIssueRequest,
)
from core.security import AuditService, JWTService, RBACPolicy


@pytest.mark.asyncio
async def test_jwt_service_and_rbac_permissions() -> None:
    jwt = JWTService(secret="test-secret")
    issued = await jwt.issue(
        TokenIssueRequest(
            subject="lead-1",
            tenant_id="tenant-a",
            roles=(SecurityRole.DELIVERY_LEAD,),
        )
    )

    principal = await jwt.verify(issued.access_token)
    access = RBACPolicy().check(
        AccessCheckRequest(
            principal=principal,
            required_permissions=(SecurityPermission.APPROVAL_REVIEW,),
        )
    )
    denied = RBACPolicy().check(
        AccessCheckRequest(
            principal=principal,
            required_permissions=(SecurityPermission.SECURITY_ADMIN,),
        )
    )

    assert principal.subject == "lead-1"
    assert access.allowed is True
    assert denied.allowed is False
    assert SecurityPermission.SECURITY_ADMIN in denied.missing_permissions


@pytest.mark.asyncio
async def test_audit_events_are_hash_chained_and_immutable() -> None:
    audit = AuditService()

    first = await audit.record(
        AuditEvent(
            type=AuditEventType.WORKFLOW_EXECUTION,
            actor="developer",
            action="workflow_started",
            workflow_id=__import__("uuid").uuid4(),
        )
    )
    second = await audit.record(
        AuditEvent(
            type=AuditEventType.AGENT_EXECUTION,
            actor="qa",
            action="agent_completed",
            agent_name="qa",
        )
    )
    events = await audit.query(AuditQuery(limit=10))

    assert first.event_hash
    assert second.previous_hash == first.event_hash
    assert events == (first, second)
    with pytest.raises(ValueError):
        await audit.record(first)


def test_security_and_audit_apis_issue_tokens_check_access_and_query_events() -> None:
    client = TestClient(create_app())

    token_response = client.post(
        "/auth/token",
        json={
            "subject": "admin-1",
            "tenant_id": "tenant-sec",
            "roles": ["platform_admin"],
            "expires_in_seconds": 3600,
        },
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["authenticated"] is True
    assert me_response.json()["principal"]["subject"] == "admin-1"

    access_response = client.post(
        "/auth/check",
        json={"required_permissions": ["security:admin"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert access_response.status_code == 200
    assert access_response.json()["allowed"] is True

    audit_response = client.post(
        "/audit/events",
        json={
            "type": "prompt_changed",
            "actor": "admin-1",
            "tenant_id": "tenant-sec",
            "action": "prompt_saved",
            "resource": "prompt/dev",
            "payload": {"version": 2},
        },
    )
    assert audit_response.status_code == 201
    event = audit_response.json()["event"]
    assert event["event_hash"]

    events_response = client.get("/audit/events?actor=admin-1")
    assert events_response.status_code == 200
    assert any(item["type"] == "prompt_changed" for item in events_response.json()["events"])
