"""Bug memory APIs."""

from typing import Any
from uuid import UUID

from core.contracts.memory import BugMemoryRecord, MemoryNamespace, MemoryQuery, MemoryScope
from core.memory.repository import MemoryRepository


class BugMemory:
    """Stores defects, regressions, and known issues."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def record(
        self,
        key: str,
        title: str,
        value: dict[str, Any],
        workflow_id: UUID | None = None,
        agent_name: str | None = None,
        severity: str = "medium",
        status: str = "open",
        tags: tuple[str, ...] = tuple(),
    ) -> BugMemoryRecord:
        record = BugMemoryRecord(
            scope=MemoryScope.WORKFLOW if workflow_id else MemoryScope.GLOBAL,
            key=key,
            title=title,
            value=value,
            workflow_id=workflow_id,
            agent_name=agent_name,
            severity=severity,
            status=status,
            tags=tags,
        )
        stored = await self._repository.put(record)
        return BugMemoryRecord.model_validate(stored)

    async def search(self, query: MemoryQuery | None = None) -> tuple[BugMemoryRecord, ...]:
        base_query = query or MemoryQuery()
        records = await self._repository.query(
            base_query.model_copy(update={"namespace": MemoryNamespace.BUG})
        )
        return tuple(BugMemoryRecord.model_validate(record) for record in records)
