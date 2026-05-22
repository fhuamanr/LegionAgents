"""FastAPI adapter for multi-workspace management."""

from pathlib import Path
from uuid import UUID

from app.schemas import (
    ProjectCreateApiRequest,
    WorkspaceCreateApiRequest,
    WorkspaceIsolationResponse,
    WorkspaceListResponse,
    WorkspaceProjectListResponse,
    WorkspaceProjectResponse,
    WorkspaceResponse,
)
from core.contracts.workspaces import (
    ProjectCreateRequest,
    RepositoryBinding,
    RepositoryBindingProvider,
    WorkspaceAgentConfig,
    WorkspaceCreateRequest,
)
from core.workspaces import WorkspaceManagementService


class WorkspaceManagementApplicationService:
    """API-facing multi-workspace service."""

    def __init__(self, service: WorkspaceManagementService | None = None) -> None:
        self._service = service or WorkspaceManagementService()

    async def create_workspace(self, request: WorkspaceCreateApiRequest) -> WorkspaceResponse:
        workspace = await self._service.create_workspace(
            WorkspaceCreateRequest(
                tenant_id=request.tenant_id,
                name=request.name,
                description=request.description,
                created_by=request.created_by,
                storage_root=Path(request.storage_root) if request.storage_root else None,
                agents=tuple(WorkspaceAgentConfig.model_validate(agent.model_dump()) for agent in request.agents),
                metadata=request.metadata,
            )
        )
        return WorkspaceResponse(workspace=workspace.model_dump(mode="json"))

    async def list_workspaces(self, tenant_id: str | None = None) -> WorkspaceListResponse:
        workspaces = await self._service.list_workspaces(tenant_id)
        return WorkspaceListResponse(workspaces=tuple(workspace.model_dump(mode="json") for workspace in workspaces))

    async def get_workspace(self, workspace_id: UUID) -> WorkspaceResponse:
        workspace = await self._service.get_workspace(workspace_id)
        return WorkspaceResponse(workspace=workspace.model_dump(mode="json"))

    async def create_project(self, workspace_id: UUID, request: ProjectCreateApiRequest) -> WorkspaceProjectResponse:
        project = await self._service.create_project(
            workspace_id,
            ProjectCreateRequest(
                name=request.name,
                description=request.description,
                repositories=tuple(
                    RepositoryBinding(
                        name=repository.name,
                        provider=RepositoryBindingProvider(repository.provider),
                        uri=repository.uri,
                        path=Path(repository.path) if repository.path else None,
                        default_branch=repository.default_branch,
                        metadata=repository.metadata,
                    )
                    for repository in request.repositories
                ),
                metadata=request.metadata,
            ),
        )
        return WorkspaceProjectResponse(project=project.model_dump(mode="json"))

    async def list_projects(self, workspace_id: UUID) -> WorkspaceProjectListResponse:
        projects = await self._service.list_projects(workspace_id)
        return WorkspaceProjectListResponse(projects=tuple(project.model_dump(mode="json") for project in projects))

    async def isolation_summary(self, workspace_id: UUID) -> WorkspaceIsolationResponse:
        isolation = await self._service.isolation_summary(workspace_id)
        return WorkspaceIsolationResponse(isolation=isolation.model_dump(mode="json"))
