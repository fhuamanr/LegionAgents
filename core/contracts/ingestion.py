"""Contracts for user story ingestion."""

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata
from core.contracts.outputs import AcceptanceCriterion, UserStory


class IngestionSourceType(StrEnum):
    """Supported and planned ingestion source types."""

    MARKDOWN = "markdown"
    TEXT = "txt"
    DOCX = "docx"
    PDF = "pdf"
    JIRA = "jira"
    NOTION = "notion"


class RequirementCategory(StrEnum):
    """Requirement classification categories."""

    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATA = "data"
    INTEGRATION = "integration"
    UX = "ux"
    TESTING = "testing"
    UNKNOWN = "unknown"


class IngestionValidationSeverity(StrEnum):
    """Severity for ingestion validation findings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IngestionSource(ContractBaseModel):
    """A story ingestion source."""

    source_type: IngestionSourceType
    path: Path | None = None
    uri: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(ContractBaseModel):
    """Raw parsed document content before story extraction."""

    source: IngestionSource
    text: str = ""
    sections: tuple["NormalizedSection", ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedSection(ContractBaseModel):
    """Normalized document section."""

    title: str
    level: int = Field(default=1, ge=1)
    content: str = ""
    order: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RequirementClassification(ContractBaseModel):
    """Classification result for a requirement or story."""

    category: RequirementCategory
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)
    signals: tuple[str, ...] = Field(default_factory=tuple)


class ExtractedEpic(ContractBaseModel):
    """Epic detected during ingestion."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    story_ids: tuple[str, ...] = Field(default_factory=tuple)
    classification: RequirementClassification | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedStory(ContractBaseModel):
    """User story with ingestion metadata."""

    story: UserStory
    epic_id: str | None = None
    source_section: str | None = None
    classification: RequirementClassification = Field(
        default_factory=lambda: RequirementClassification(
            category=RequirementCategory.UNKNOWN,
            confidence=0.0,
            rationale="No classification was produced.",
        )
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionValidationIssue(ContractBaseModel):
    """Validation issue produced by the ingestion engine."""

    severity: IngestionValidationSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    story_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryIngestionResult(ContractBaseModel):
    """Structured output of the ingestion pipeline."""

    id: UUID = Field(default_factory=uuid4)
    source: IngestionSource
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    epics: tuple[ExtractedEpic, ...] = Field(default_factory=tuple)
    stories: tuple[ExtractedStory, ...] = Field(default_factory=tuple)
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = Field(default_factory=tuple)
    validation_issues: tuple[IngestionValidationIssue, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def valid(self) -> bool:
        """Whether the result has no validation errors."""

        return not any(issue.severity == IngestionValidationSeverity.ERROR for issue in self.validation_issues)


ParsedDocument.model_rebuild()
