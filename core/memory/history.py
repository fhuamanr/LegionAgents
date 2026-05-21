"""Execution history memory."""

from typing import Any
from uuid import UUID

from core.contracts.memory import (
    ExecutionHistoryRecord,
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
)
from core.memory.repository import MemoryRepository


class ExecutionHistoryMemory:
    """Stores execution events for workflows, threads, and agents."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def append(
        self,
        event_name: str,
        value: dict[str, Any],
        workflow_id: UUID,
        agent_name: str | None = None,
        thread_id: str | None = None,
        tags: tuple[str, ...] = tuple(),
    ) -> ExecutionHistoryRecord:
        record = ExecutionHistoryRecord(
            scope=MemoryScope.WORKFLOW,
            key=event_name,
            value=value,
            event_name=event_name,
            workflow_id=workflow_id,
            agent_name=agent_name,
            thread_id=thread_id,
            tags=tags,
        )
        stored = await self._repository.put(record)
        return ExecutionHistoryRecord.model_validate(stored)

    async def list_for_workflow(
        self,
        workflow_id: UUID,
        agent_name: str | None = None,
    ) -> tuple[ExecutionHistoryRecord, ...]:
        records = await self._repository.query(
            MemoryQuery(
                namespace=MemoryNamespace.EXECUTION_HISTORY,
                workflow_id=workflow_id,
                agent_name=agent_name,
            )
        )
        return tuple(ExecutionHistoryRecord.model_validate(record) for record in records)

