"""Telemetry hooks for developer runtime execution."""

from abc import ABC, abstractmethod
from typing import Any


class DeveloperTelemetryHook(ABC):
    """Telemetry boundary for developer runtime events."""

    @abstractmethod
    async def emit(self, event_name: str, attributes: dict[str, Any]) -> None:
        """Emit a telemetry event."""


class NoopDeveloperTelemetryHook(DeveloperTelemetryHook):
    """No-op telemetry hook."""

    async def emit(self, event_name: str, attributes: dict[str, Any]) -> None:
        return None

