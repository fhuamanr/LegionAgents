"""Contracts for observability, telemetry, metrics, tracing, and analytics."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class MetricKind(StrEnum):
    """Metric instrument kinds."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class TraceSpanStatus(StrEnum):
    """Trace span status."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class ErrorSeverity(StrEnum):
    """Error tracking severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricPoint(ContractBaseModel):
    """Provider-neutral metric point."""

    name: str = Field(min_length=1)
    kind: MetricKind
    value: float
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(ContractBaseModel):
    """Token usage telemetry."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class PromptTelemetry(ContractBaseModel):
    """Prompt size telemetry."""

    message_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)


class TraceSpan(ContractBaseModel):
    """OpenTelemetry-ready trace span model."""

    trace_id: UUID = Field(default_factory=uuid4)
    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    name: str = Field(min_length=1)
    workflow_id: UUID | None = None
    execution_id: UUID | None = None
    agent_name: str | None = None
    status: TraceSpanStatus = TraceSpanStatus.UNSET
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        """Duration in milliseconds."""

        if self.ended_at is None:
            return None
        return round((self.ended_at - self.started_at).total_seconds() * 1000, 2)


class ErrorRecord(ContractBaseModel):
    """Structured error tracking record."""

    id: UUID = Field(default_factory=uuid4)
    message: str = Field(min_length=1)
    severity: ErrorSeverity
    workflow_id: UUID | None = None
    execution_id: UUID | None = None
    agent_name: str | None = None
    exception_type: str | None = None
    stacktrace: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentAnalytics(ContractBaseModel):
    """Aggregated analytics for one agent."""

    agent_name: str = Field(min_length=1)
    executions_started: int = Field(default=0, ge=0)
    executions_completed: int = Field(default=0, ge=0)
    failures: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    qa_rejections: int = Field(default=0, ge=0)
    average_execution_time_ms: float = Field(default=0, ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    prompt_telemetry: PromptTelemetry = Field(default_factory=PromptTelemetry)


class WorkflowAnalytics(ContractBaseModel):
    """Aggregated workflow analytics."""

    workflow_id: UUID
    duration_ms: float = Field(default=0, ge=0)
    agent_count: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    failures: int = Field(default=0, ge=0)
    qa_rejection_rate: float = Field(default=0, ge=0, le=1)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    prompt_telemetry: PromptTelemetry = Field(default_factory=PromptTelemetry)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservabilitySnapshot(ContractBaseModel):
    """Complete observability snapshot."""

    metrics: tuple[MetricPoint, ...] = Field(default_factory=tuple)
    spans: tuple[TraceSpan, ...] = Field(default_factory=tuple)
    errors: tuple[ErrorRecord, ...] = Field(default_factory=tuple)
    workflow_analytics: tuple[WorkflowAnalytics, ...] = Field(default_factory=tuple)
    agent_analytics: tuple[AgentAnalytics, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
