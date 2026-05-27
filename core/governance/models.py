"""Governance policy models."""

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class RuleEffect(StrEnum):
    """Governance rule effect."""

    REQUIRE = "require"
    FORBID = "forbid"
    RECOMMEND = "recommend"


class RulePriority(StrEnum):
    """Governance rule priority."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class GovernanceSeverity(StrEnum):
    """Runtime enforcement severity for a governance rule."""

    INFO = "info"
    WARNING = "warning"
    NEEDS_REVIEW = "needs_review"
    BLOCKING = "blocking"


class RuleCategory(StrEnum):
    """Governance categories enforced by the platform."""

    SECURITY = "security"
    CODING_STANDARDS = "coding_standards"
    ARCHITECTURE = "architecture"
    QA = "qa"
    DOCUMENTATION = "documentation"
    AGENT_BOUNDARY = "agent_boundary"
    GENERAL = "general"


class RuleSource(StrEnum):
    """Origin of a governance rule."""

    GLOBAL_DEFAULT = "global_default"
    ENTERPRISE_STANDARD = "enterprise_standard"
    AGENT_LOCAL = "agent_local"
    RUNTIME_EDITED = "runtime_edited"
    FUTURE_YAML = "future_yaml"


class GovernanceRule(ContractBaseModel):
    """Single governance rule."""

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    effect: RuleEffect
    category: RuleCategory = RuleCategory.GENERAL
    priority: RulePriority = RulePriority.NORMAL
    source: RuleSource = RuleSource.GLOBAL_DEFAULT
    allow_local_override: bool = False
    severity: GovernanceSeverity = GovernanceSeverity.BLOCKING
    source_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicy(ContractBaseModel):
    """Governance policy for a global, enterprise, or agent scope."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    rules: tuple[GovernanceRule, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceValidationResult(ContractBaseModel):
    """Policy validation result."""

    valid: bool
    errors: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceViolation(ContractBaseModel):
    """Evidence-based governance finding emitted during runtime checks."""

    rule_id: str = Field(min_length=1)
    severity: GovernanceSeverity
    evidence: str = ""
    matched_text: str = ""
    reason: str = Field(min_length=1)
    suggested_fix: str = ""
    blocking: bool = False

