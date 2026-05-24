"""Execution event bus."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from uuid import UUID

from core.persistence import PostgresJsonDocumentStore
from core.streaming.models import ExecutionEvent, ExecutionEventType


class ExecutionEventBus(ABC):
    """Async pub/sub boundary for execution events."""

    @abstractmethod
    async def publish(self, event: ExecutionEvent) -> None:
        """Publish an event."""

    @abstractmethod
    async def history(
        self,
        workflow_id: UUID | None = None,
        event_type: ExecutionEventType | None = None,
    ) -> tuple[ExecutionEvent, ...]:
        """Return event history."""

    @abstractmethod
    async def subscribe(
        self,
        workflow_id: UUID | None = None,
    ) -> AsyncIterator[ExecutionEvent]:
        """Subscribe to live events."""


class InMemoryExecutionEventBus(ExecutionEventBus):
    """Local in-memory event bus for tests and future WebSocket adapters."""

    def __init__(self) -> None:
        self._events: list[ExecutionEvent] = []
        self._subscribers: list[asyncio.Queue[ExecutionEvent]] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self._events.append(event)
        for queue in list(self._subscribers):
            await queue.put(event)

    async def history(
        self,
        workflow_id: UUID | None = None,
        event_type: ExecutionEventType | None = None,
    ) -> tuple[ExecutionEvent, ...]:
        return tuple(
            event
            for event in self._events
            if (workflow_id is None or event.workflow_id == workflow_id)
            and (event_type is None or event.type == event_type)
        )

    async def subscribe(
        self,
        workflow_id: UUID | None = None,
    ) -> AsyncIterator[ExecutionEvent]:
        queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if workflow_id is None or event.workflow_id == workflow_id:
                    yield event
        finally:
            self._subscribers.remove(queue)


class PostgresBackedExecutionEventBus(ExecutionEventBus):
    """Execution event bus with PostgreSQL persistence and in-memory live fanout."""

    _bucket = "execution_events"

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store
        self._memory = InMemoryExecutionEventBus()

    async def publish(self, event: ExecutionEvent) -> None:
        await self._memory.publish(event)
        key = f"{str(event.workflow_id or 'none')}:{event.timestamp.isoformat()}:{str(event.id)}"
        await self._store.upsert(
            bucket=self._bucket,
            document_id=event.id,
            key=key,
            payload=event.model_dump(mode="json"),
        )

    async def history(
        self,
        workflow_id: UUID | None = None,
        event_type: ExecutionEventType | None = None,
    ) -> tuple[ExecutionEvent, ...]:
        persisted = tuple(
            ExecutionEvent.model_validate(payload)
            for payload in await self._store.list(bucket=self._bucket)
        )
        return tuple(
            event
            for event in persisted
            if (workflow_id is None or event.workflow_id == workflow_id)
            and (event_type is None or event.type == event_type)
        )

    async def subscribe(
        self,
        workflow_id: UUID | None = None,
    ) -> AsyncIterator[ExecutionEvent]:
        async for event in self._memory.subscribe(workflow_id=workflow_id):
            yield event

