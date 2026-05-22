"""Metrics registry and aggregation."""

from collections import defaultdict
from datetime import datetime, timezone

from core.contracts.observability import MetricKind, MetricPoint


class MetricsRegistry:
    """In-memory metric registry with provider-neutral points."""

    def __init__(self) -> None:
        self._points: list[MetricPoint] = []
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    async def increment(
        self,
        name: str,
        value: float = 1,
        labels: dict[str, str] | None = None,
        metadata: dict | None = None,
    ) -> MetricPoint:
        """Increment a counter metric."""

        labels = labels or {}
        key = (name, tuple(sorted(labels.items())))
        self._counters[key] += value
        point = MetricPoint(
            name=name,
            kind=MetricKind.COUNTER,
            value=self._counters[key],
            labels=labels,
            metadata=metadata or {},
        )
        self._points.append(point)
        return point

    async def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        metadata: dict | None = None,
    ) -> MetricPoint:
        """Record a gauge metric."""

        point = MetricPoint(
            name=name,
            kind=MetricKind.GAUGE,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._points.append(point)
        return point

    async def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        metadata: dict | None = None,
    ) -> MetricPoint:
        """Record a histogram observation."""

        point = MetricPoint(
            name=name,
            kind=MetricKind.HISTOGRAM,
            value=value,
            labels=labels or {},
            metadata=metadata or {},
        )
        self._points.append(point)
        return point

    async def points(self) -> tuple[MetricPoint, ...]:
        """Return all metric points."""

        return tuple(self._points)
