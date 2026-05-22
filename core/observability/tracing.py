"""Tracing infrastructure."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from core.contracts.observability import TraceSpan, TraceSpanStatus


class InMemoryTracer:
    """OpenTelemetry-ready in-memory tracer."""

    def __init__(self) -> None:
        self._spans: dict[UUID, TraceSpan] = {}

    async def start_span(
        self,
        name: str,
        workflow_id: UUID | None = None,
        execution_id: UUID | None = None,
        agent_name: str | None = None,
        parent_span_id: UUID | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Start a trace span."""

        span = TraceSpan(
            name=name,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=agent_name,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        self._spans[span.span_id] = span
        return span

    async def end_span(
        self,
        span_id: UUID,
        status: TraceSpanStatus = TraceSpanStatus.OK,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """End a trace span."""

        span = self._spans[span_id]
        ended = span.model_copy(
            update={
                "status": status,
                "ended_at": datetime.now(timezone.utc),
                "attributes": {**span.attributes, **(attributes or {})},
            }
        )
        self._spans[span_id] = ended
        return ended

    async def spans(self) -> tuple[TraceSpan, ...]:
        """Return all trace spans."""

        return tuple(self._spans.values())
