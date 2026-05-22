"""Contracts for human approval workflow gates."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata


class ApprovalGateType(StrEnum):
    """Approval gate categories."""

    MANUAL_REVIEW = "manual_review"
    RETRY_APPROVAL = "retry_approval"
    PR_APPROVAL = "pr_approval"
    QA_OVERRIDE = "qa_override"
    RELEASE_APPROVAL = "release_approval"


class ApprovalStatus(StrEnum):
    """Approval lifecycle status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WorkflowPauseReason(StrEnum):
    """Reasons a workflow can pause."""

    AWAITING_APPROVAL = "awaiting_approval"
    QA_OVERRIDE_REQUIRED = "qa_override_required"
    RETRY_REQUIRES_APPROVAL = "retry_requires_approval"
    PR_REVIEW_REQUIRED = "pr_review_required"


class ApprovalDecision(StrEnum):
    """Reviewer decision."""

    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"


class Reviewer(ContractBaseModel):
    """Human reviewer identity."""

    reviewer_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    email: str | None = None
    role: str | None = None


class ApprovalRequest(ContractBaseModel):
    """Request to create an approval gate."""

    workflow_id: UUID
    gate_type: ApprovalGateType
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    required_reviewers: tuple[Reviewer, ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: WorkflowPauseReason = WorkflowPauseReason.AWAITING_APPROVAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRecord(ContractBaseModel):
    """Persistent approval gate record."""

    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    gate_type: ApprovalGateType
    status: ApprovalStatus = ApprovalStatus.PENDING
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    required_reviewers: tuple[Reviewer, ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: WorkflowPauseReason = WorkflowPauseReason.AWAITING_APPROVAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: Reviewer | None = None
    decision_reason: str | None = None
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionRequest(ContractBaseModel):
    """Reviewer decision request."""

    decision: ApprovalDecision
    reviewer: Reviewer
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowPause(ContractBaseModel):
    """Workflow pause state caused by an approval gate."""

    workflow_id: UUID
    approval_id: UUID
    reason: WorkflowPauseReason
    paused_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resume_token: UUID = Field(default_factory=uuid4)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResumeDecision(ContractBaseModel):
    """Resume decision produced after approval handling."""

    workflow_id: UUID
    approval_id: UUID
    can_resume: bool
    route_signal: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalQuery(ContractBaseModel):
    """Approval query filters."""

    workflow_id: UUID | None = None
    status: ApprovalStatus | None = None
    gate_type: ApprovalGateType | None = None
    reviewer_id: str | None = None
