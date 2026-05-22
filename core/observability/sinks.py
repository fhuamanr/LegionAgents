"""Telemetry sinks that bridge execution events into observability."""

from core.contracts.observability import ErrorRecord, ErrorSeverity, TraceSpanStatus
from core.observability.metrics import MetricsRegistry
from core.observability.tracing import InMemoryTracer
from core.streaming.models import ExecutionEvent, ExecutionEventType
from core.streaming.telemetry import TelemetrySink


class ObservabilityTelemetrySink(TelemetrySink):
    """Records execution events as metrics, traces, and error records."""

    def __init__(self, metrics: MetricsRegistry, tracer: InMemoryTracer) -> None:
        self._metrics = metrics
        self._tracer = tracer
        self._errors: list[ErrorRecord] = []

    async def record(self, event: ExecutionEvent) -> None:
        """Record one execution event."""

        labels = {
            "event_type": event.type.value,
            "agent": event.agent_name or "unknown",
        }
        await self._metrics.increment("execution_events_total", labels=labels)

        if event.type == ExecutionEventType.AGENT_STARTED:
            await self._metrics.increment("agent_executions_started_total", labels={"agent": event.agent_name or "unknown"})
            await self._tracer.start_span(
                name=f"agent.{event.agent_name or 'unknown'}",
                workflow_id=event.workflow_id,
                execution_id=event.execution_id,
                agent_name=event.agent_name,
                attributes=event.payload,
            )
        elif event.type == ExecutionEventType.AGENT_COMPLETED:
            await self._metrics.increment("agent_executions_completed_total", labels={"agent": event.agent_name or "unknown"})
            await self._observe_duration(event)
        elif event.type == ExecutionEventType.RETRY_STARTED:
            await self._metrics.increment("agent_retries_total", labels={"agent": event.agent_name or "unknown"})
        elif event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}:
            await self._metrics.increment("agent_failures_total", labels={"agent": event.agent_name or "unknown"})
            if event.type == ExecutionEventType.QA_FAILED:
                await self._metrics.increment("qa_rejections_total", labels={"agent": "qa"})
            self._errors.append(
                ErrorRecord(
                    message=event.message or "Execution failure.",
                    severity=ErrorSeverity.ERROR,
                    workflow_id=event.workflow_id,
                    execution_id=event.execution_id,
                    agent_name=event.agent_name,
                    metadata=event.payload,
                )
            )

        await self._record_token_and_prompt_metrics(event)

    async def errors(self) -> tuple[ErrorRecord, ...]:
        """Return tracked errors."""

        return tuple(self._errors)

    async def _observe_duration(self, event: ExecutionEvent) -> None:
        duration = event.payload.get("duration_ms")
        if isinstance(duration, int | float):
            await self._metrics.observe(
                "agent_execution_duration_ms",
                float(duration),
                labels={"agent": event.agent_name or "unknown"},
            )

    async def _record_token_and_prompt_metrics(self, event: ExecutionEvent) -> None:
        token_usage = event.payload.get("token_usage")
        if isinstance(token_usage, dict):
            await self._metrics.increment(
                "tokens_total",
                float(token_usage.get("total_tokens", 0)),
                labels={"agent": event.agent_name or "unknown"},
            )
        prompt = event.payload.get("prompt")
        if isinstance(prompt, dict):
            await self._metrics.observe(
                "prompt_size_estimated_tokens",
                float(prompt.get("estimated_tokens", 0)),
                labels={"agent": event.agent_name or "unknown"},
            )
