"""API schemas."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base API response model."""

    model_config = ConfigDict(extra="forbid")


class WorkflowStatus(StrEnum):
    """Workflow API status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class HealthResponse(ApiModel):
    status: str
    service: str


class UserStoryUploadRequest(ApiModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(ApiModel):
    upload_id: UUID
    title: str
    received_at: datetime


class TriggerWorkflowRequest(ApiModel):
    task: str = Field(min_length=1)
    upload_id: UUID | None = None
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(ApiModel):
    workflow_id: UUID
    status: WorkflowStatus
    task: str
    thread_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionStatusResponse(ApiModel):
    workflow_id: UUID
    status: WorkflowStatus
    active_agent: str | None = None
    progress_percent: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionLogResponse(ApiModel):
    workflow_id: UUID
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class AgentStatusResponse(ApiModel):
    agents: dict[str, WorkflowStatus]


class ReportResponse(ApiModel):
    workflow_id: UUID
    kind: str
    content: dict[str, Any] = Field(default_factory=dict)


class StoredUpload(ApiModel):
    upload_id: UUID = Field(default_factory=uuid4)
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewerRequest(ApiModel):
    reviewer_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    email: str | None = None
    role: str | None = None


class CreateApprovalRequest(ApiModel):
    workflow_id: UUID
    gate_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    required_reviewers: tuple[ReviewerRequest, ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: str = "awaiting_approval"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionApiRequest(ApiModel):
    decision: str = Field(min_length=1)
    reviewer: ReviewerRequest
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalResponse(ApiModel):
    approval_id: UUID
    workflow_id: UUID
    gate_type: str
    status: str
    title: str
    description: str
    requested_by: str
    required_reviewers: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: str
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
    decided_by: dict[str, Any] | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalListResponse(ApiModel):
    approvals: tuple[ApprovalResponse, ...] = Field(default_factory=tuple)


class WorkflowPauseResponse(ApiModel):
    workflow_id: UUID
    approval_id: UUID
    reason: str
    paused_at: datetime
    resume_token: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResumeResponse(ApiModel):
    workflow_id: UUID
    approval_id: UUID
    can_resume: bool
    route_signal: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservabilitySnapshotResponse(ApiModel):
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowAnalyticsResponse(ApiModel):
    workflow_id: UUID
    analytics: dict[str, Any] = Field(default_factory=dict)


class AgentAnalyticsResponse(ApiModel):
    agents: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceConfigUpsertRequest(ApiModel):
    scope: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    markdown: str = ""
    agent_name: str | None = None
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceRollbackApiRequest(ApiModel):
    target_version: int = Field(ge=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None


class GovernanceConfigResponse(ApiModel):
    document: dict[str, Any]
    latest_version: dict[str, Any] | None = None
    reload_event: dict[str, Any] | None = None


class GovernanceConfigListResponse(ApiModel):
    documents: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceVersionListResponse(ApiModel):
    versions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceReloadHistoryResponse(ApiModel):
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
