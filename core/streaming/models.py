"""Streaming execution models."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class ExecutionEventType(StrEnum):
    """Structured execution event types."""

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    RETRY_STARTED = "retry_started"
    QA_FAILED = "QA_failed"
    PR_GENERATED = "PR_generated"
    DOCS_GENERATED = "docs_generated"
    LOG_EMITTED = "log_emitted"
    PROGRESS_UPDATED = "progress_updated"
    TOKEN_STREAMED = "token_streamed"
    OUTPUT_GENERATED = "output_generated"
    TELEMETRY_RECORDED = "telemetry_recorded"


class ExecutionLogLevel(StrEnum):
    """Structured log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExecutionEvent(ContractBaseModel):
    """WebSocket-ready structured execution event."""

    id: UUID = Field(default_factory=uuid4)
    type: ExecutionEventType
    workflow_id: UUID | None = None
    execution_id: UUID | None = None
    thread_id: str | None = None
    agent_name: str | None = None
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionProgress(ContractBaseModel):
    """Progress snapshot for a workflow or agent execution."""

    workflow_id: UUID
    completed_steps: int = Field(default=0, ge=0)
    total_steps: int = Field(default=0, ge=0)
    active_agent: str | None = None
    failed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def percent(self) -> float:
        """Progress percentage."""

        if self.total_steps == 0:
            return 0.0
        return round((self.completed_steps / self.total_steps) * 100, 2)


class TimelineEntry(ContractBaseModel):
    """Timeline entry derived from execution events."""

    event_id: UUID
    event_type: ExecutionEventType
    timestamp: datetime
    agent_name: str | None = None
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionTimeline(ContractBaseModel):
    """Execution timeline for one workflow."""

    workflow_id: UUID
    entries: tuple[TimelineEntry, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

