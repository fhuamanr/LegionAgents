"""Autonomous repository engine."""

from core.repository.diff import DiffAnalyzer
from core.repository.git import GitService
from core.repository.metadata import RepositorySummarizer
from core.repository.providers import GitHubRepositoryProvider, GitLabRepositoryProvider, RepositoryProviderAdapter
from core.repository.runtime import RepositoryRuntime
from core.repository.security import GitCommandPolicy
from core.repository.workspace import IsolatedWorkspaceManager

__all__ = [
    "DiffAnalyzer",
    "GitCommandPolicy",
    "GitHubRepositoryProvider",
    "GitLabRepositoryProvider",
    "GitService",
    "IsolatedWorkspaceManager",
    "RepositoryProviderAdapter",
    "RepositoryRuntime",
    "RepositorySummarizer",
]
