"""Contracts for autonomous pull request review."""

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata
from core.contracts.repository import DiffAnalysis, PullRequestPreparation
from core.contracts.repository_intelligence import RepositoryIntelligenceReport


class PRReviewCategory(StrEnum):
    """Review validation categories."""

    ARCHITECTURE = "architecture"
    CODING_STANDARDS = "coding_standards"
    QA = "qa"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    REPOSITORY = "repository"


class PRReviewSeverity(StrEnum):
    """Review comment severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MergeReadiness(StrEnum):
    """Merge readiness classification."""

    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    NEEDS_WORK = "needs_work"
    BLOCKED = "blocked"


class PRReviewRequest(ContractBaseModel):
    """Request to review a prepared pull request or diff."""

    pull_request: PullRequestPreparation | None = None
    diff: DiffAnalysis | None = None
    repository_root: Path | None = None
    repository_intelligence: RepositoryIntelligenceReport | None = None
    title: str | None = None
    description: str | None = None
    author: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PRReviewComment(ContractBaseModel):
    """Automated structured PR review comment."""

    id: UUID = Field(default_factory=uuid4)
    category: PRReviewCategory
    severity: PRReviewSeverity
    message: str = Field(min_length=1)
    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    rule_id: str | None = None
    recommendation: str | None = None
    blocking: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PRValidationResult(ContractBaseModel):
    """Validation result for one review layer."""

    category: PRReviewCategory
    passed: bool
    comments: tuple[PRReviewComment, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PRReviewScore(ContractBaseModel):
    """Merge readiness score."""

    score: float = Field(ge=0.0, le=100.0)
    readiness: MergeReadiness
    blocking_count: int = Field(default=0, ge=0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PRReviewReport(ContractBaseModel):
    """Complete autonomous PR review report."""

    id: UUID = Field(default_factory=uuid4)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    title: str
    summary: str
    score: PRReviewScore
    comments: tuple[PRReviewComment, ...] = Field(default_factory=tuple)
    validations: tuple[PRValidationResult, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
