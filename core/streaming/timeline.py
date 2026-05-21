"""Execution timeline generation."""

from uuid import UUID

from core.streaming.bus import ExecutionEventBus
from core.streaming.models import ExecutionTimeline, TimelineEntry


class TimelineGenerator:
    """Builds execution timelines from event history."""

    def __init__(self, event_bus: ExecutionEventBus) -> None:
        self._event_bus = event_bus

    async def generate(self, workflow_id: UUID) -> ExecutionTimeline:
        events = await self._event_bus.history(workflow_id=workflow_id)
        entries = tuple(
            TimelineEntry(
                event_id=event.id,
                event_type=event.type,
                timestamp=event.timestamp,
                agent_name=event.agent_name,
                message=event.message,
                payload=event.payload,
            )
            for event in sorted(events, key=lambda item: item.timestamp)
        )
        return ExecutionTimeline(
            workflow_id=workflow_id,
            entries=entries,
            metadata={"entry_count": len(entries)},
        )

