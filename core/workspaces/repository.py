"""Workspace persistence abstractions."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from core.contracts.workspaces import Workspace, WorkspaceProject


class WorkspaceRepository(ABC):
    """Persistence boundary for workspaces and projects."""

    @abstractmethod
    async def save_workspace(self, workspace: Workspace) -> Workspace:
        """Create or replace a workspace."""

    @abstractmethod
    async def get_workspace(self, workspace_id: UUID) -> Workspace:
        """Get one workspace."""

    @abstractmethod
    async def list_workspaces(self, tenant_id: str | None = None) -> tuple[Workspace, ...]:
        """List workspaces."""

    @abstractmethod
    async def save_project(self, project: WorkspaceProject) -> WorkspaceProject:
        """Create or replace a project."""

    @abstractmethod
    async def list_projects(self, workspace_id: UUID) -> tuple[WorkspaceProject, ...]:
        """List projects for a workspace."""


class InMemoryWorkspaceRepository(WorkspaceRepository):
    """In-memory workspace repository for local development and tests."""

    def __init__(self) -> None:
        self._workspaces: dict[UUID, Workspace] = {}
        self._projects: dict[UUID, WorkspaceProject] = {}

    async def save_workspace(self, workspace: Workspace) -> Workspace:
        stored = workspace.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._workspaces[stored.id] = stored
        return stored

    async def get_workspace(self, workspace_id: UUID) -> Workspace:
        return self._workspaces[workspace_id]

    async def list_workspaces(self, tenant_id: str | None = None) -> tuple[Workspace, ...]:
        return tuple(
            workspace
            for workspace in sorted(self._workspaces.values(), key=lambda item: (item.tenant_id, item.name))
            if tenant_id is None or workspace.tenant_id == tenant_id
        )

    async def save_project(self, project: WorkspaceProject) -> WorkspaceProject:
        stored = project.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._projects[stored.id] = stored
        return stored

    async def list_projects(self, workspace_id: UUID) -> tuple[WorkspaceProject, ...]:
        return tuple(
            project
            for project in sorted(self._projects.values(), key=lambda item: item.name)
            if project.workspace_id == workspace_id
        )
