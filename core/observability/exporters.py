"""Exporter boundaries for observability providers."""

import json

from core.contracts.observability import MetricKind, MetricPoint, ObservabilitySnapshot, TraceSpan


class PrometheusMetricsExporter:
    """Prometheus-ready text exposition exporter."""

    def export(self, metrics: tuple[MetricPoint, ...]) -> str:
        """Export metrics in a Prometheus-compatible text shape."""

        lines: list[str] = []
        for point in metrics:
            metric_name = point.name.replace(".", "_").replace("-", "_")
            labels = self._labels(point.labels)
            if point.kind == MetricKind.HISTOGRAM:
                lines.append(f"{metric_name}_sum{labels} {point.value}")
                lines.append(f"{metric_name}_count{labels} 1")
            else:
                lines.append(f"{metric_name}{labels} {point.value}")
        return "\n".join(lines) + ("\n" if lines else "")

    def _labels(self, labels: dict[str, str]) -> str:
        if not labels:
            return ""
        content = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
        return f"{{{content}}}"


class OpenTelemetrySpanExporter:
    """OpenTelemetry-ready span payload exporter."""

    def export(self, spans: tuple[TraceSpan, ...]) -> tuple[dict, ...]:
        """Export spans to an OTLP-like dictionary shape."""

        return tuple(
            {
                "trace_id": str(span.trace_id),
                "span_id": str(span.span_id),
                "parent_span_id": str(span.parent_span_id) if span.parent_span_id else None,
                "name": span.name,
                "status": span.status.value,
                "start_time_unix_nano": int(span.started_at.timestamp() * 1_000_000_000),
                "end_time_unix_nano": int(span.ended_at.timestamp() * 1_000_000_000) if span.ended_at else None,
                "attributes": span.attributes,
            }
            for span in spans
        )


class DatadogTelemetryExporter:
    """Datadog-ready JSON exporter."""

    def export(self, snapshot: ObservabilitySnapshot) -> str:
        """Export a snapshot in a Datadog-ingestable JSON shape."""

        return json.dumps(
            {
                "series": [metric.model_dump(mode="json") for metric in snapshot.metrics],
                "spans": [span.model_dump(mode="json") for span in snapshot.spans],
                "errors": [error.model_dump(mode="json") for error in snapshot.errors],
                "analytics": {
                    "workflows": [item.model_dump(mode="json") for item in snapshot.workflow_analytics],
                    "agents": [item.model_dump(mode="json") for item in snapshot.agent_analytics],
                },
            },
            indent=2,
        )


class GrafanaDashboardModelBuilder:
    """Builds a Grafana-ready dashboard model descriptor."""

    def build(self) -> dict:
        """Return a dashboard model skeleton for future provisioning."""

        panels = [
            "Agent execution time",
            "Retries",
            "Failures",
            "QA rejection rate",
            "Workflow duration",
            "Token usage",
            "Prompt sizes",
        ]
        return {
            "title": "Multi-Agent Delivery Observability",
            "tags": ["multi-agent", "langgraph", "delivery"],
            "timezone": "browser",
            "panels": [{"title": title, "type": "timeseries"} for title in panels],
        }
