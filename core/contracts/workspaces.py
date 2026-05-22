"""Contracts for tenant-aware multi-workspace project management."""

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class WorkspaceRole(StrEnum):
    """Workspace permission roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkspacePermission(StrEnum):
    """Workspace permission capabilities."""

    MANAGE_WORKSPACE = "manage_workspace"
    MANAGE_PROJECTS = "manage_projects"
    MANAGE_REPOSITORIES = "manage_repositories"
    MANAGE_AGENTS = "manage_agents"
    RUN_WORKFLOWS = "run_workflows"
    VIEW_WORKFLOWS = "view_workflows"
    VIEW_MEMORY = "view_memory"


class RepositoryBindingProvider(StrEnum):
    """Repository binding provider."""

    LOCAL = "local"
    GITHUB = "github"
    GITLAB = "gitlab"
    MOUNTED = "mounted"


class WorkspaceConfiguration(ContractBaseModel):
    """Workspace-specific execution, storage, governance, and memory configuration."""

    storage_root: Path
    memory_namespace: str
    governance_namespace: str
    default_branch: str = "main"
    environment: str = "local"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAgentConfig(ContractBaseModel):
    """Agent enablement and configuration scoped to a workspace."""

    agent_name: str = Field(min_length=1)
    enabled: bool = True
    prompt_profile: str | None = None
    governance_profile: str | None = None
    max_retries: int = Field(default=2, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceMember(ContractBaseModel):
    """Workspace member and permission assignment."""

    user_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    role: WorkspaceRole = WorkspaceRole.MEMBER
    permissions: tuple[WorkspacePermission, ...] = Field(default_factory=tuple)
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RepositoryBinding(ContractBaseModel):
    """Repository associated with a workspace project."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    provider: RepositoryBindingProvider = RepositoryBindingProvider.LOCAL
    uri: str | None = None
    path: Path | None = None
    default_branch: str = "main"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkspaceProject(ContractBaseModel):
    """Project inside a workspace."""

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    name: str = Field(min_length=1)
    description: str = ""
    repositories: tuple[RepositoryBinding, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Workspace(ContractBaseModel):
    """Tenant-aware isolated workspace."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    configuration: WorkspaceConfiguration
    members: tuple[WorkspaceMember, ...] = Field(default_factory=tuple)
    agents: tuple[WorkspaceAgentConfig, ...] = Field(default_factory=tuple)
    project_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreateRequest(ContractBaseModel):
    """Create workspace request."""

    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    created_by: str = Field(default="workspace-admin", min_length=1)
    storage_root: Path | None = None
    agents: tuple[WorkspaceAgentConfig, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectCreateRequest(ContractBaseModel):
    """Create project request."""

    name: str = Field(min_length=1)
    description: str = ""
    repositories: tuple[RepositoryBinding, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceIsolationSummary(ContractBaseModel):
    """Computed isolation metadata for a workspace."""

    workspace_id: UUID
    tenant_id: str
    storage_root: Path
    memory_namespace: str
    governance_namespace: str
    project_count: int = Field(ge=0)
    repository_count: int = Field(ge=0)
    enabled_agents: tuple[str, ...] = Field(default_factory=tuple)
