"""ADR memory APIs."""

from typing import Any
from uuid import UUID

from core.contracts.memory import ADRMemoryRecord, MemoryNamespace, MemoryQuery, MemoryScope
from core.memory.repository import MemoryRepository


class ADRMemory:
    """Stores architecture decision records."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def record(
        self,
        key: str,
        title: str,
        value: dict[str, Any],
        workflow_id: UUID | None = None,
        status: str = "proposed",
        tags: tuple[str, ...] = tuple(),
    ) -> ADRMemoryRecord:
        record = ADRMemoryRecord(
            scope=MemoryScope.WORKFLOW if workflow_id else MemoryScope.GLOBAL,
            key=key,
            title=title,
            value=value,
            workflow_id=workflow_id,
            status=status,
            tags=tags,
        )
        stored = await self._repository.put(record)
        return ADRMemoryRecord.model_validate(stored)

    async def search(self, query: MemoryQuery | None = None) -> tuple[ADRMemoryRecord, ...]:
        base_query = query or MemoryQuery()
        records = await self._repository.query(
            base_query.model_copy(update={"namespace": MemoryNamespace.ADR})
        )
        return tuple(ADRMemoryRecord.model_validate(record) for record in records)

