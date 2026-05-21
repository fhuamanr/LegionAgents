"""Telemetry hooks for QA runtime execution."""

from abc import ABC, abstractmethod
from typing import Any


class QATelemetryHook(ABC):
    """Telemetry boundary for QA runtime events."""

    @abstractmethod
    async def emit(self, event_name: str, attributes: dict[str, Any]) -> None:
        """Emit a telemetry event."""


class NoopQATelemetryHook(QATelemetryHook):
    """No-op QA telemetry hook."""

    async def emit(self, event_name: str, attributes: dict[str, Any]) -> None:
        return None

