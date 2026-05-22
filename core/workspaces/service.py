"""Tenant-aware workspace management service."""

from pathlib import Path
from uuid import UUID

from core.contracts.workspaces import (
    ProjectCreateRequest,
    Workspace,
    WorkspaceAgentConfig,
    WorkspaceConfiguration,
    WorkspaceCreateRequest,
    WorkspaceIsolationSummary,
    WorkspaceMember,
    WorkspacePermission,
    WorkspaceProject,
    WorkspaceRole,
)
from core.workspaces.repository import InMemoryWorkspaceRepository, WorkspaceRepository


class WorkspaceManagementService:
    """Coordinates isolated workspace, project, repository, and agent configuration."""

    _default_agents = ("ba", "architect", "developer", "qa", "docs", "pr")

    def __init__(self, repository: WorkspaceRepository | None = None, storage_base: Path | None = None) -> None:
        self._repository = repository or InMemoryWorkspaceRepository()
        self._storage_base = storage_base or Path.cwd() / "outputs" / "workspaces"

    async def create_workspace(self, request: WorkspaceCreateRequest) -> Workspace:
        workspace_id_hint = self._slug(request.name)
        storage_root = request.storage_root or self._storage_base / request.tenant_id / workspace_id_hint
        workspace = Workspace(
            tenant_id=request.tenant_id,
            name=request.name,
            description=request.description,
            configuration=WorkspaceConfiguration(
                storage_root=storage_root,
                memory_namespace=f"{request.tenant_id}:{workspace_id_hint}:memory",
                governance_namespace=f"{request.tenant_id}:{workspace_id_hint}:governance",
            ),
            members=(
                WorkspaceMember(
                    user_id=request.created_by,
                    display_name=request.created_by,
                    role=WorkspaceRole.OWNER,
                    permissions=tuple(WorkspacePermission),
                ),
            ),
            agents=request.agents or self._default_agent_configs(),
            metadata=request.metadata,
        )
        return await self._repository.save_workspace(workspace)

    async def list_workspaces(self, tenant_id: str | None = None) -> tuple[Workspace, ...]:
        return await self._repository.list_workspaces(tenant_id)

    async def get_workspace(self, workspace_id: UUID) -> Workspace:
        return await self._repository.get_workspace(workspace_id)

    async def create_project(self, workspace_id: UUID, request: ProjectCreateRequest) -> WorkspaceProject:
        workspace = await self.get_workspace(workspace_id)
        project = await self._repository.save_project(
            WorkspaceProject(
                workspace_id=workspace.id,
                name=request.name,
                description=request.description,
                repositories=request.repositories,
                metadata=request.metadata,
            )
        )
        workspace = workspace.model_copy(update={"project_ids": tuple((*workspace.project_ids, project.id))})
        await self._repository.save_workspace(workspace)
        return project

    async def list_projects(self, workspace_id: UUID) -> tuple[WorkspaceProject, ...]:
        return await self._repository.list_projects(workspace_id)

    async def isolation_summary(self, workspace_id: UUID) -> WorkspaceIsolationSummary:
        workspace = await self.get_workspace(workspace_id)
        projects = await self.list_projects(workspace_id)
        repository_count = sum(len(project.repositories) for project in projects)
        return WorkspaceIsolationSummary(
            workspace_id=workspace.id,
            tenant_id=workspace.tenant_id,
            storage_root=workspace.configuration.storage_root,
            memory_namespace=workspace.configuration.memory_namespace,
            governance_namespace=workspace.configuration.governance_namespace,
            project_count=len(projects),
            repository_count=repository_count,
            enabled_agents=tuple(agent.agent_name for agent in workspace.agents if agent.enabled),
        )

    def _default_agent_configs(self) -> tuple[WorkspaceAgentConfig, ...]:
        return tuple(WorkspaceAgentConfig(agent_name=agent) for agent in self._default_agents)

    def _slug(self, value: str) -> str:
        slug = "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")
        return slug or "workspace"
