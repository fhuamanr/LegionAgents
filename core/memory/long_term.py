"""Long-term memory APIs."""

from typing import Any
from uuid import UUID

from core.contracts.memory import (
    LongTermMemoryRecord,
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
)
from core.memory.repository import MemoryRepository


class LongTermMemory:
    """Durable memory service for reusable knowledge."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def remember(
        self,
        key: str,
        value: dict[str, Any],
        scope: MemoryScope,
        agent_name: str | None = None,
        workflow_id: UUID | None = None,
        thread_id: str | None = None,
        importance: float = 0.5,
        tags: tuple[str, ...] = tuple(),
    ) -> LongTermMemoryRecord:
        record = LongTermMemoryRecord(
            scope=scope,
            key=key,
            value=value,
            agent_name=agent_name,
            workflow_id=workflow_id,
            thread_id=thread_id,
            importance=importance,
            tags=tags,
        )
        stored = await self._repository.put(record)
        return LongTermMemoryRecord.model_validate(stored)

    async def recall(self, query: MemoryQuery) -> tuple[LongTermMemoryRecord, ...]:
        records = await self._repository.query(
            query.model_copy(update={"namespace": MemoryNamespace.LONG_TERM})
        )
        return tuple(LongTermMemoryRecord.model_validate(record) for record in records)

