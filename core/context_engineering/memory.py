"""Memory-aware context providers."""

from core.contracts.context import ContextPriority
from core.contracts.memory import MemoryNamespace, MemoryQuery, MemoryScope, VectorMemoryQuery
from core.context_engineering.models import ContextEngineeringRequest, ContextItem, ContextItemSource
from core.memory import MemorySystem


class MemoryContextProvider:
    """Retrieves scoped memory for context engineering."""

    def __init__(self, memory_system: MemorySystem | None = None) -> None:
        self._memory_system = memory_system

    async def provide(self, request: ContextEngineeringRequest) -> tuple[ContextItem, ...]:
        if self._memory_system is None or not request.config.enable_memory:
            return tuple()

        records = await self._memory_system.repository.query(
            MemoryQuery(
                agent_name=request.agent_name,
                workflow_id=request.workflow_id,
                thread_id=request.thread_id,
                limit=10,
            )
        )
        items = [
            ContextItem(
                id=f"memory-{record.id}",
                source=ContextItemSource.MEMORY,
                title=f"Memory: {record.key}",
                content=str(record.value),
                priority=ContextPriority.NORMAL,
                token_hint=max(1, len(str(record.value)) // 4),
                metadata={
                    "agent_name": record.agent_name,
                    "requested_agent": request.agent_name,
                    "namespace": record.namespace.value,
                },
            )
            for record in records
            if record.scope in {MemoryScope.AGENT, MemoryScope.THREAD, MemoryScope.WORKFLOW}
            and (record.agent_name is None or record.agent_name == request.agent_name)
        ]

        vector_results = await self._memory_system.vector.search(
            VectorMemoryQuery(
                text=request.task,
                agent_name=request.agent_name,
                workflow_id=request.workflow_id,
                thread_id=request.thread_id,
                limit=5,
            )
        )
        items.extend(
            ContextItem(
                id=f"vector-memory-{result.record.id}",
                source=ContextItemSource.VECTOR_MEMORY,
                title=f"Vector Memory: {result.record.key}",
                content=result.record.text,
                priority=ContextPriority.NORMAL,
                token_hint=max(1, len(result.record.text) // 4),
                metadata={
                    "agent_name": result.record.agent_name,
                    "requested_agent": request.agent_name,
                    "namespace": MemoryNamespace.VECTOR.value,
                    "score": result.score,
                },
            )
            for result in vector_results
            if result.record.agent_name is None or result.record.agent_name == request.agent_name
        )
        return tuple(items)
