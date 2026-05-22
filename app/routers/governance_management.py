"""Dynamic governance management APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_governance_management_service
from app.schemas import (
    GovernanceConfigListResponse,
    GovernanceConfigResponse,
    GovernanceConfigUpsertRequest,
    GovernanceReloadHistoryResponse,
    GovernanceRollbackApiRequest,
    GovernanceVersionListResponse,
)
from app.services.governance_management_service import GovernanceManagementApplicationService

router = APIRouter(prefix="/governance/configs", tags=["governance"])


@router.get("", response_model=GovernanceConfigListResponse)
async def list_governance_configs(
    scope: str | None = None,
    agent_name: str | None = None,
    kind: str | None = None,
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceConfigListResponse:
    return await service.list(scope=scope, agent_name=agent_name, kind=kind)


@router.post("", response_model=GovernanceConfigResponse, status_code=201)
async def save_governance_config(
    request: GovernanceConfigUpsertRequest,
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceConfigResponse:
    return await service.save(request)


@router.get("/reloads", response_model=GovernanceReloadHistoryResponse)
async def get_governance_reload_history(
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceReloadHistoryResponse:
    return await service.reload_history()


@router.get("/{document_id}", response_model=GovernanceConfigResponse)
async def get_governance_config(
    document_id: UUID,
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceConfigResponse:
    return await service.get(document_id)


@router.get("/{document_id}/versions", response_model=GovernanceVersionListResponse)
async def get_governance_versions(
    document_id: UUID,
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceVersionListResponse:
    return await service.versions(document_id)


@router.post("/{document_id}/rollback", response_model=GovernanceConfigResponse)
async def rollback_governance_config(
    document_id: UUID,
    request: GovernanceRollbackApiRequest,
    service: GovernanceManagementApplicationService = Depends(get_governance_management_service),
) -> GovernanceConfigResponse:
    return await service.rollback(document_id, request)
