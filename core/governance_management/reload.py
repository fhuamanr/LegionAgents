"""Real-time reload support for governance configuration."""

from core.contracts.governance_management import GovernanceReloadEvent


class GovernanceReloadBus:
    """In-memory reload event bus for future WebSocket delivery."""

    def __init__(self) -> None:
        self._events: list[GovernanceReloadEvent] = []

    async def publish(self, event: GovernanceReloadEvent) -> GovernanceReloadEvent:
        """Publish a reload event."""

        self._events.append(event)
        return event

    async def history(self) -> tuple[GovernanceReloadEvent, ...]:
        """Return reload event history."""

        return tuple(self._events)
