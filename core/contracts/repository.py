"""Contracts for autonomous repository runtime operations."""

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata


class RepositoryProvider(StrEnum):
    """Repository hosting providers."""

    LOCAL = "local"
    GITHUB = "github"
    GITLAB = "gitlab"
    UNKNOWN = "unknown"


class RepositoryAgentConsumer(StrEnum):
    """Agents supported by the repository runtime."""

    DEVELOPER = "developer"
    QA = "qa"
    DOCS = "docs"


class RepositoryChangeKind(StrEnum):
    """Git change kind."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNMERGED = "unmerged"
    UNKNOWN = "unknown"


class RepositoryWorkspace(ContractBaseModel):
    """Isolated repository workspace."""

    id: UUID = Field(default_factory=uuid4)
    root_path: Path
    repository_path: Path
    agent_name: str
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryCloneRequest(ContractBaseModel):
    """Clone request for an isolated workspace."""

    repository_url: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    branch: str | None = None
    depth: int | None = Field(default=1, ge=1)
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BranchCreationRequest(ContractBaseModel):
    """Branch creation request."""

    branch_name: str = Field(min_length=1)
    start_point: str | None = None


class CommitGenerationRequest(ContractBaseModel):
    """Commit request over the current workspace changes."""

    message: str
    author_name: str = "AI Delivery Platform"
    author_email: str = "ai-delivery-platform@example.local"
    include_all: bool = True


class GitCommandResult(ContractBaseModel):
    """Result from a secure git command."""

    command: tuple[str, ...]
    cwd: Path
    return_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def succeeded(self) -> bool:
        """Whether the command succeeded."""

        return self.return_code == 0


class DiffFileChange(ContractBaseModel):
    """Single file change derived from git diff metadata."""

    path: str = Field(min_length=1)
    kind: RepositoryChangeKind = RepositoryChangeKind.UNKNOWN
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    previous_path: str | None = None
    language: str | None = None


class DiffAnalysis(ContractBaseModel):
    """Repository diff analysis."""

    base_ref: str | None = None
    target_ref: str | None = None
    files: tuple[DiffFileChange, ...] = Field(default_factory=tuple)
    summary: str = ""
    risk_flags: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryMetadata(ContractBaseModel):
    """Repository metadata extracted from a workspace."""

    provider: RepositoryProvider = RepositoryProvider.UNKNOWN
    remote_url: str | None = None
    current_branch: str | None = None
    head_sha: str | None = None
    is_dirty: bool = False
    detected_languages: tuple[str, ...] = Field(default_factory=tuple)
    file_count: int = Field(default=0, ge=0)
    test_paths: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositorySummary(ContractBaseModel):
    """Repository summary for agent context."""

    metadata: RepositoryMetadata
    top_level_directories: tuple[str, ...] = Field(default_factory=tuple)
    notable_files: tuple[str, ...] = Field(default_factory=tuple)
    summary: str = ""


class PullRequestPreparation(ContractBaseModel):
    """PR preparation package before provider-specific creation."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_branch: str = Field(min_length=1)
    target_branch: str = Field(min_length=1)
    diff: DiffAnalysis
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryRuntimeResult(ContractBaseModel):
    """Repository runtime operation result."""

    workspace: RepositoryWorkspace
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    metadata: RepositoryMetadata | None = None
    summary: RepositorySummary | None = None
    diff: DiffAnalysis | None = None
    pull_request: PullRequestPreparation | None = None
    git_results: tuple[GitCommandResult, ...] = Field(default_factory=tuple)
