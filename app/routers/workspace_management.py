"""Multi-workspace management APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_workspace_management_service
from app.schemas import (
    ProjectCreateApiRequest,
    WorkspaceCreateApiRequest,
    WorkspaceIsolationResponse,
    WorkspaceListResponse,
    WorkspaceProjectListResponse,
    WorkspaceProjectResponse,
    WorkspaceResponse,
)
from app.services.workspace_management_service import WorkspaceManagementApplicationService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    tenant_id: str | None = None,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceListResponse:
    return await service.list_workspaces(tenant_id)


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    request: WorkspaceCreateApiRequest,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    return await service.create_workspace(request)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    return await service.get_workspace(workspace_id)


@router.get("/{workspace_id}/isolation", response_model=WorkspaceIsolationResponse)
async def get_workspace_isolation(
    workspace_id: UUID,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceIsolationResponse:
    return await service.isolation_summary(workspace_id)


@router.get("/{workspace_id}/projects", response_model=WorkspaceProjectListResponse)
async def list_workspace_projects(
    workspace_id: UUID,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceProjectListResponse:
    return await service.list_projects(workspace_id)


@router.post("/{workspace_id}/projects", response_model=WorkspaceProjectResponse, status_code=201)
async def create_workspace_project(
    workspace_id: UUID,
    request: ProjectCreateApiRequest,
    service: WorkspaceManagementApplicationService = Depends(get_workspace_management_service),
) -> WorkspaceProjectResponse:
    return await service.create_project(workspace_id, request)
