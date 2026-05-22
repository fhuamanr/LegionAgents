"""Tenant-aware multi-workspace management."""

from core.workspaces.repository import InMemoryWorkspaceRepository, WorkspaceRepository
from core.workspaces.service import WorkspaceManagementService

__all__ = [
    "InMemoryWorkspaceRepository",
    "WorkspaceManagementService",
    "WorkspaceRepository",
]
