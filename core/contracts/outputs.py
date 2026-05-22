"""Structured output contracts for specialized agents."""

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.base import ContractBaseModel, ContractVersion, TraceMetadata


class OutputContractKind(StrEnum):
    """Output contract families mapped to agent responsibilities."""

    BA_REQUIREMENTS = "ba_requirements"
    ARCHITECTURE_DECISION = "architecture_decision"
    DEVELOPMENT_PLAN = "development_plan"
    QUALITY_REPORT = "quality_report"
    DOCUMENTATION_PACKAGE = "documentation_package"
    PULL_REQUEST_PACKAGE = "pull_request_package"
    GENERIC = "generic"


class OutputSeverity(StrEnum):
    """Severity levels for risks, issues, and validation findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContractFieldRequirement(ContractBaseModel):
    """Requirement for a field an agent output must provide."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True
    value_type: str = Field(default="string", min_length=1)


class OutputContract(ContractBaseModel):
    """Declarative contract expected from an agent."""

    id: UUID = Field(default_factory=uuid4)
    version: ContractVersion = ContractVersion.V1
    kind: OutputContractKind = OutputContractKind.GENERIC
    agent_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required_fields: tuple[ContractFieldRequirement, ...] = Field(default_factory=tuple)
    artifact_kinds: tuple[ArtifactKind, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskItem(ContractBaseModel):
    """Risk or issue identified by an agent."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: OutputSeverity
    description: str = Field(min_length=1)
    mitigation: str | None = None


class DependencyItem(ContractBaseModel):
    """Dependency identified in an agent output."""

    name: str = Field(min_length=1)
    owner_agent: str | None = None
    description: str = Field(min_length=1)
    blocking: bool = False


class AcceptanceCriterion(ContractBaseModel):
    """Business acceptance criterion owned by BA output."""

    id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)


class UserStory(ContractBaseModel):
    """INVEST-style user story."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    narrative: str = Field(min_length=1)
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = Field(default_factory=tuple)
    dependencies: tuple[DependencyItem, ...] = Field(default_factory=tuple)
    risks: tuple[RiskItem, ...] = Field(default_factory=tuple)


class ArchitectureDecision(ContractBaseModel):
    """Architecture decision output owned by the architect agent."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    context: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    consequences: tuple[str, ...] = Field(default_factory=tuple)
    constraints: tuple[str, ...] = Field(default_factory=tuple)


class DevelopmentWorkItem(ContractBaseModel):
    """Implementation work item owned by the developer agent."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_paths: tuple[str, ...] = Field(default_factory=tuple)
    test_expectations: tuple[str, ...] = Field(default_factory=tuple)


class CodeChangeProposal(ContractBaseModel):
    """Developer-owned code generation or modification proposal."""

    path: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    content: str | None = None


class TestGenerationProposal(ContractBaseModel):
    """Developer-owned test generation proposal."""

    path: str = Field(min_length=1)
    test_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    command: str | None = None
    content: str | None = None


class RefactoringSuggestion(ContractBaseModel):
    """Developer-owned refactoring suggestion."""

    target_path: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risk: str | None = None


class PullRequestDraft(ContractBaseModel):
    """Developer-owned PR draft content.

    This is draft text only. PR creation remains owned by the PR agent.
    """

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    checklist: tuple[str, ...] = Field(default_factory=tuple)


class QualityFinding(ContractBaseModel):
    """QA validation finding."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: OutputSeverity
    evidence: str = Field(min_length=1)
    recommendation: str | None = None


class TestReport(ContractBaseModel):
    """QA test report summary."""

    name: str = Field(min_length=1)
    test_type: str = Field(min_length=1)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    command: str | None = None
    details: str | None = None


class ScreenshotEvidence(ContractBaseModel):
    """Screenshot evidence generated by QA automation."""

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ExecutionLog(ContractBaseModel):
    """QA execution log entry."""

    message: str = Field(min_length=1)
    level: str = Field(default="info", min_length=1)
    source: str | None = None


class BugSummary(ContractBaseModel):
    """Bug summary owned by the QA agent."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: OutputSeverity
    reproduction_steps: tuple[str, ...] = Field(default_factory=tuple)
    expected: str | None = None
    actual: str | None = None
    evidence: tuple[ScreenshotEvidence, ...] = Field(default_factory=tuple)


class CoverageSummary(ContractBaseModel):
    """Coverage summary produced by QA."""

    lines: float | None = Field(default=None, ge=0, le=100)
    branches: float | None = Field(default=None, ge=0, le=100)
    functions: float | None = Field(default=None, ge=0, le=100)
    statements: float | None = Field(default=None, ge=0, le=100)
    details: str | None = None


class DocumentationItem(ContractBaseModel):
    """Documentation deliverable entry."""

    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    content_summary: str = Field(min_length=1)
    artifact: Artifact | None = None


class AgentStructuredOutput(ContractBaseModel):
    """Base structured output emitted by any specialized agent."""

    id: UUID = Field(default_factory=uuid4)
    contract_kind: OutputContractKind = OutputContractKind.GENERIC
    agent_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    risks: tuple[RiskItem, ...] = Field(default_factory=tuple)
    dependencies: tuple[DependencyItem, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BARequirementsOutput(AgentStructuredOutput):
    """BA output contract."""

    contract_kind: OutputContractKind = OutputContractKind.BA_REQUIREMENTS
    user_stories: tuple[UserStory, ...] = Field(default_factory=tuple)


class ArchitectOutput(AgentStructuredOutput):
    """Architect output contract."""

    contract_kind: OutputContractKind = OutputContractKind.ARCHITECTURE_DECISION
    decisions: tuple[ArchitectureDecision, ...] = Field(default_factory=tuple)


class DeveloperOutput(AgentStructuredOutput):
    """Developer output contract."""

    contract_kind: OutputContractKind = OutputContractKind.DEVELOPMENT_PLAN
    work_items: tuple[DevelopmentWorkItem, ...] = Field(default_factory=tuple)
    code_changes: tuple[CodeChangeProposal, ...] = Field(default_factory=tuple)
    tests: tuple[TestGenerationProposal, ...] = Field(default_factory=tuple)
    refactoring_suggestions: tuple[RefactoringSuggestion, ...] = Field(default_factory=tuple)
    commit_message: str | None = None
    pr_draft: PullRequestDraft | None = None


class QAOutput(AgentStructuredOutput):
    """QA output contract."""

    contract_kind: OutputContractKind = OutputContractKind.QUALITY_REPORT
    findings: tuple[QualityFinding, ...] = Field(default_factory=tuple)
    test_reports: tuple[TestReport, ...] = Field(default_factory=tuple)
    screenshots: tuple[ScreenshotEvidence, ...] = Field(default_factory=tuple)
    execution_logs: tuple[ExecutionLog, ...] = Field(default_factory=tuple)
    bug_summaries: tuple[BugSummary, ...] = Field(default_factory=tuple)
    coverage: CoverageSummary | None = None
    passed: bool = False


class DocsOutput(AgentStructuredOutput):
    """Documentation output contract."""

    contract_kind: OutputContractKind = OutputContractKind.DOCUMENTATION_PACKAGE
    documents: tuple[DocumentationItem, ...] = Field(default_factory=tuple)


class PullRequestOutput(AgentStructuredOutput):
    """Pull request output contract."""

    contract_kind: OutputContractKind = OutputContractKind.PULL_REQUEST_PACKAGE
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_branch: str = Field(min_length=1)
    source_branch: str = Field(min_length=1)
