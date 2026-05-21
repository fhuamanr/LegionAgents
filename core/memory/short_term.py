"""Short-term memory APIs."""

from typing import Any
from uuid import UUID

from core.contracts.memory import (
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
    ShortTermMemoryRecord,
)
from core.memory.repository import MemoryRepository


class ShortTermMemory:
    """Thread-aware short-term memory service."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def remember(
        self,
        key: str,
        value: dict[str, Any],
        thread_id: str,
        agent_name: str | None = None,
        workflow_id: UUID | None = None,
        tags: tuple[str, ...] = tuple(),
    ) -> ShortTermMemoryRecord:
        record = ShortTermMemoryRecord(
            scope=MemoryScope.THREAD,
            key=key,
            value=value,
            thread_id=thread_id,
            agent_name=agent_name,
            workflow_id=workflow_id,
            tags=tags,
        )
        stored = await self._repository.put(record)
        return ShortTermMemoryRecord.model_validate(stored)

    async def recall(
        self,
        thread_id: str,
        agent_name: str | None = None,
        limit: int | None = None,
    ) -> tuple[ShortTermMemoryRecord, ...]:
        records = await self._repository.query(
            MemoryQuery(
                namespace=MemoryNamespace.SHORT_TERM,
                scope=MemoryScope.THREAD,
                thread_id=thread_id,
                agent_name=agent_name,
                limit=limit,
            )
        )
        return tuple(ShortTermMemoryRecord.model_validate(record) for record in records)

