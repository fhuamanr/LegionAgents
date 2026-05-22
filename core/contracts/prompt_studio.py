"""Contracts for Prompt Engineering Studio."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class PromptScope(StrEnum):
    """Prompt ownership scope."""

    GLOBAL = "global"
    AGENT = "agent"
    WORKFLOW = "workflow"


class PromptStatus(StrEnum):
    """Prompt lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PromptVariable(ContractBaseModel):
    """Prompt variable definition."""

    name: str = Field(min_length=1)
    description: str | None = None
    required: bool = True
    default: str | None = None


class PromptDocument(ContractBaseModel):
    """Editable prompt document."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    scope: PromptScope = PromptScope.AGENT
    agent_name: str | None = None
    markdown: str = ""
    variables: tuple[PromptVariable, ...] = Field(default_factory=tuple)
    status: PromptStatus = PromptStatus.DRAFT
    version: int = Field(default=1, ge=1)
    updated_by: str = Field(default="system", min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptVersion(ContractBaseModel):
    """Version history entry for a prompt document."""

    id: UUID = Field(default_factory=uuid4)
    prompt_id: UUID
    version: int = Field(ge=1)
    markdown: str
    variables: tuple[PromptVariable, ...] = Field(default_factory=tuple)
    changed_by: str = Field(min_length=1)
    change_summary: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptUpsert(ContractBaseModel):
    """Create or update prompt request."""

    name: str = Field(min_length=1)
    scope: PromptScope = PromptScope.AGENT
    agent_name: str | None = None
    markdown: str = ""
    variables: tuple[PromptVariable, ...] = Field(default_factory=tuple)
    status: PromptStatus = PromptStatus.DRAFT
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptRollbackRequest(ContractBaseModel):
    """Rollback prompt to a previous version."""

    target_version: int = Field(ge=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None


class PromptPreviewRequest(ContractBaseModel):
    """Render prompt with variables injected."""

    markdown: str
    variables: dict[str, str] = Field(default_factory=dict)


class PromptPreview(ContractBaseModel):
    """Rendered prompt preview."""

    rendered: str
    missing_variables: tuple[str, ...] = Field(default_factory=tuple)
    estimated_tokens: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)


class PromptTestRequest(ContractBaseModel):
    """Prompt live test request."""

    prompt_id: UUID | None = None
    markdown: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    test_input: str = ""
    expected_output: str | None = None
    evaluator_notes: str | None = None


class PromptEvaluation(ContractBaseModel):
    """Prompt evaluation signals."""

    score: float = Field(ge=0.0, le=100.0)
    passed: bool
    findings: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptTestResult(ContractBaseModel):
    """Prompt test result with execution preview."""

    preview: PromptPreview
    execution_preview: str
    evaluation: PromptEvaluation


class PromptComparisonResult(ContractBaseModel):
    """Prompt comparison result."""

    left_version: int | None = None
    right_version: int | None = None
    added_lines: tuple[str, ...] = Field(default_factory=tuple)
    removed_lines: tuple[str, ...] = Field(default_factory=tuple)
    changed_line_count: int = Field(default=0, ge=0)
    token_delta: int = 0
