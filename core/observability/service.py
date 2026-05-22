"""Observability service coordinating metrics, traces, and analytics."""

from uuid import UUID

from core.contracts.observability import ObservabilitySnapshot
from core.observability.analytics import ObservabilityAnalyticsEngine
from core.observability.exporters import (
    DatadogTelemetryExporter,
    GrafanaDashboardModelBuilder,
    OpenTelemetrySpanExporter,
    PrometheusMetricsExporter,
)
from core.observability.metrics import MetricsRegistry
from core.observability.sinks import ObservabilityTelemetrySink
from core.observability.tracing import InMemoryTracer
from core.streaming.bus import ExecutionEventBus
from core.streaming.models import ExecutionEvent


class ObservabilityService:
    """Provider-neutral observability facade."""

    def __init__(
        self,
        event_bus: ExecutionEventBus,
        metrics: MetricsRegistry | None = None,
        tracer: InMemoryTracer | None = None,
        analytics: ObservabilityAnalyticsEngine | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._recorded_event_ids: set[str] = set()
        self.metrics = metrics or MetricsRegistry()
        self.tracer = tracer or InMemoryTracer()
        self.analytics = analytics or ObservabilityAnalyticsEngine()
        self.sink = ObservabilityTelemetrySink(self.metrics, self.tracer)
        self.prometheus = PrometheusMetricsExporter()
        self.otel = OpenTelemetrySpanExporter()
        self.datadog = DatadogTelemetryExporter()
        self.grafana = GrafanaDashboardModelBuilder()

    async def record_event(self, event: ExecutionEvent) -> None:
        """Record one event into observability stores."""

        event_id = str(event.id)
        if event_id in self._recorded_event_ids:
            return
        await self.sink.record(event)
        self._recorded_event_ids.add(event_id)

    async def rebuild_from_history(self) -> None:
        """Replay event history into observability stores."""

        for event in await self._event_bus.history():
            await self.record_event(event)

    async def snapshot(self, workflow_id: UUID | None = None) -> ObservabilitySnapshot:
        """Return an observability snapshot."""

        await self.rebuild_from_history()
        events = await self._event_bus.history(workflow_id=workflow_id)
        workflow_analytics = await self.analytics.workflow_analytics(events)
        agent_analytics = await self.analytics.agent_analytics(events)
        return ObservabilitySnapshot(
            metrics=await self.metrics.points(),
            spans=await self.tracer.spans(),
            errors=await self.sink.errors(),
            workflow_analytics=workflow_analytics,
            agent_analytics=agent_analytics,
            metadata={
                "opentelemetry_ready": True,
                "datadog_ready": True,
                "prometheus_ready": True,
                "grafana_ready": True,
            },
        )

    async def prometheus_text(self) -> str:
        """Return Prometheus text exposition."""

        return self.prometheus.export(await self.metrics.points())

    async def datadog_json(self) -> str:
        """Return Datadog-ready JSON."""

        return self.datadog.export(await self.snapshot())

    async def otel_spans(self) -> tuple[dict, ...]:
        """Return OpenTelemetry-ready spans."""

        return self.otel.export(await self.tracer.spans())
