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

