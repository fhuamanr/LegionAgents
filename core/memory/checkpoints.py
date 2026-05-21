"""LangGraph checkpoint-compatible memory APIs."""

from typing import Any

from core.contracts.memory import (
    CheckpointMemoryRecord,
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
)
from core.memory.repository import MemoryRepository


class CheckpointMemory:
    """Stores checkpoint payloads using thread-aware keys."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def put_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: dict[str, Any],
        parent_checkpoint_id: str | None = None,
    ) -> CheckpointMemoryRecord:
        record = CheckpointMemoryRecord(
            scope=MemoryScope.THREAD,
            key=checkpoint_id,
            value=state,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
        )
        stored = await self._repository.put(record)
        return CheckpointMemoryRecord.model_validate(stored)

    async def get_latest(self, thread_id: str) -> CheckpointMemoryRecord | None:
        records = await self._repository.query(
            MemoryQuery(
                namespace=MemoryNamespace.CHECKPOINT,
                scope=MemoryScope.THREAD,
                thread_id=thread_id,
                limit=1,
            )
        )
        if not records:
            return None
        return CheckpointMemoryRecord.model_validate(records[-1])

    async def list_for_thread(self, thread_id: str) -> tuple[CheckpointMemoryRecord, ...]:
        records = await self._repository.query(
            MemoryQuery(
                namespace=MemoryNamespace.CHECKPOINT,
                scope=MemoryScope.THREAD,
                thread_id=thread_id,
            )
        )
        return tuple(CheckpointMemoryRecord.model_validate(record) for record in records)

