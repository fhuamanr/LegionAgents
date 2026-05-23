"""Tenant-aware multi-workspace management."""

from core.workspaces.repository import InMemoryWorkspaceRepository, PostgresWorkspaceRepository, WorkspaceRepository
from core.workspaces.service import WorkspaceManagementService

__all__ = [
    "InMemoryWorkspaceRepository",
    "PostgresWorkspaceRepository",
    "WorkspaceManagementService",
    "WorkspaceRepository",
]
