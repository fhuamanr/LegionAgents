"""Contracts for dynamic governance management."""

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class GovernanceConfigScope(StrEnum):
    """Governance configuration scope."""

    GLOBAL = "global"
    AGENT = "agent"


class GovernanceConfigKind(StrEnum):
    """Editable governance document kinds."""

    GRAVITY = "gravity"
    ANTI_GRAVITY = "anti_gravity"
    PERSONALITY = "personality"
    PROMPT = "prompt"
    CODING_STANDARDS = "coding_standards"
    QA_POLICY = "qa_policy"


class GovernanceReloadStatus(StrEnum):
    """Runtime reload status."""

    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


class GovernanceConfigDocument(ContractBaseModel):
    """Current governance configuration document."""

    id: UUID = Field(default_factory=uuid4)
    scope: GovernanceConfigScope
    kind: GovernanceConfigKind
    name: str = Field(min_length=1)
    markdown: str = ""
    agent_name: str | None = None
    version: int = Field(default=1, ge=1)
    source_path: Path | None = None
    updated_by: str = Field(default="system", min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceConfigVersion(ContractBaseModel):
    """Historical governance configuration version."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    version: int = Field(ge=1)
    markdown: str = ""
    changed_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceConfigUpsert(ContractBaseModel):
    """Create or update governance config request."""

    scope: GovernanceConfigScope
    kind: GovernanceConfigKind
    name: str = Field(min_length=1)
    markdown: str = ""
    agent_name: str | None = None
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceRollbackRequest(ContractBaseModel):
    """Rollback governance document to a previous version."""

    target_version: int = Field(ge=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None


class GovernanceReloadEvent(ContractBaseModel):
    """Runtime reload event for governance configuration."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    version: int
    status: GovernanceReloadStatus
    message: str = ""
    requested_by: str = Field(default="system", min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

