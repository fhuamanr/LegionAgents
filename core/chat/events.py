"""Workspace chat event bus."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from core.contracts.chat import ChatEvent


class ChatEventBus:
    """Conversation-scoped async event bus."""

    def __init__(self) -> None:
        self._events: list[ChatEvent] = []
        self._subscribers: list[asyncio.Queue[ChatEvent]] = []

    async def publish(self, event: ChatEvent) -> ChatEvent:
        """Publish a chat event."""

        self._events.append(event)
        for queue in list(self._subscribers):
            await queue.put(event)
        return event

    async def history(self, conversation_id: UUID | None = None) -> tuple[ChatEvent, ...]:
        """Return event history."""

        return tuple(event for event in self._events if conversation_id is None or event.conversation_id == conversation_id)

    async def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        """Subscribe to live chat events."""

        queue: asyncio.Queue[ChatEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if event.conversation_id == conversation_id:
                    yield event
        finally:
            self._subscribers.remove(queue)
