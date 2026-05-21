"""Execution telemetry layer."""

from abc import ABC, abstractmethod

from core.streaming.bus import ExecutionEventBus
from core.streaming.models import ExecutionEvent


class TelemetrySink(ABC):
    """Telemetry sink boundary for metrics, tracing, and WebSocket adapters."""

    @abstractmethod
    async def record(self, event: ExecutionEvent) -> None:
        """Record one execution event."""


class ExecutionTelemetryLayer:
    """Fans out event history to telemetry sinks."""

    def __init__(
        self,
        event_bus: ExecutionEventBus,
        sinks: tuple[TelemetrySink, ...] = tuple(),
    ) -> None:
        self._event_bus = event_bus
        self._sinks = sinks

    async def record_event(self, event: ExecutionEvent) -> None:
        await self._event_bus.publish(event)
        for sink in self._sinks:
            await sink.record(event)

    async def replay_history(self) -> None:
        for event in await self._event_bus.history():
            for sink in self._sinks:
                await sink.record(event)

