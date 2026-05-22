"""Security and audit APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.dependencies.container import get_security_service
from app.dependencies.security import current_principal
from app.schemas import (
    AccessCheckApiRequest,
    AccessCheckResponse,
    AuditEventCreateRequest,
    AuditEventListResponse,
    AuditEventResponse,
    TokenIssueApiRequest,
    TokenIssueResponse,
)
from app.services.security_service import SecurityApplicationService
from core.contracts.security import AuthPrincipal

router = APIRouter(tags=["security"])


@router.post("/auth/token", response_model=TokenIssueResponse)
async def issue_token(
    request: TokenIssueApiRequest,
    service: SecurityApplicationService = Depends(get_security_service),
) -> TokenIssueResponse:
    return await service.issue_token(request)


@router.get("/auth/me")
async def me(request: Request) -> dict[str, object]:
    principal = current_principal(request)
    return {"authenticated": principal is not None, "principal": principal.model_dump(mode="json") if principal else None}


@router.post("/auth/check", response_model=AccessCheckResponse)
async def check_access(
    request: AccessCheckApiRequest,
    http_request: Request,
    service: SecurityApplicationService = Depends(get_security_service),
) -> AccessCheckResponse:
    principal = current_principal(http_request) or AuthPrincipal(subject="anonymous")
    return await service.check_access(principal, request)


@router.get("/audit/events", response_model=AuditEventListResponse)
async def list_audit_events(
    type: str | None = None,
    actor: str | None = None,
    tenant_id: str | None = None,
    workspace_id: UUID | None = None,
    workflow_id: UUID | None = None,
    agent_name: str | None = None,
    limit: int = 100,
    service: SecurityApplicationService = Depends(get_security_service),
) -> AuditEventListResponse:
    return await service.query_audit_events(
        type=type,
        actor=actor,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        workflow_id=workflow_id,
        agent_name=agent_name,
        limit=limit,
    )


@router.post("/audit/events", response_model=AuditEventResponse, status_code=201)
async def create_audit_event(
    request: AuditEventCreateRequest,
    service: SecurityApplicationService = Depends(get_security_service),
) -> AuditEventResponse:
    return await service.record_audit_event(request)
