"""Workspace persistence abstractions."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from core.contracts.workspaces import Workspace, WorkspaceProject
from core.persistence import PostgresJsonDocumentStore


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


class PostgresWorkspaceRepository(WorkspaceRepository):
    """PostgreSQL-backed workspace and project persistence."""

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store

    async def save_workspace(self, workspace: Workspace) -> Workspace:
        stored = workspace.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        await self._store.upsert(
            bucket="workspaces",
            document_id=stored.id,
            key=f"{stored.tenant_id}:{stored.name}",
            payload=stored.model_dump(mode="json"),
        )
        return stored

    async def get_workspace(self, workspace_id: UUID) -> Workspace:
        return Workspace.model_validate(await self._store.get(bucket="workspaces", document_id=workspace_id))

    async def list_workspaces(self, tenant_id: str | None = None) -> tuple[Workspace, ...]:
        workspaces = tuple(
            Workspace.model_validate(item)
            for item in await self._store.list(bucket="workspaces")
        )
        return tuple(
            workspace
            for workspace in sorted(workspaces, key=lambda item: (item.tenant_id, item.name))
            if tenant_id is None or workspace.tenant_id == tenant_id
        )

    async def save_project(self, project: WorkspaceProject) -> WorkspaceProject:
        stored = project.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        await self._store.upsert(
            bucket="workspace_projects",
            document_id=stored.id,
            key=f"{stored.workspace_id}:{stored.name}",
            payload=stored.model_dump(mode="json"),
        )
        return stored

    async def list_projects(self, workspace_id: UUID) -> tuple[WorkspaceProject, ...]:
        projects = tuple(
            WorkspaceProject.model_validate(item)
            for item in await self._store.list(bucket="workspace_projects", key_prefix=f"{workspace_id}:")
        )
        return tuple(sorted(projects, key=lambda item: item.name))
