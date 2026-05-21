"""Memory repository abstractions and local in-memory persistence."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from core.contracts.memory import (
    MemoryNamespace,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
)


class MemoryRepository(ABC):
    """Async memory boundary for agents, threads, and workflows."""

    @abstractmethod
    async def put(self, record: MemoryRecord) -> MemoryRecord:
        """Create or replace a memory record."""

    @abstractmethod
    async def get(
        self,
        key: str,
        scope: MemoryScope,
        agent_name: str | None = None,
    ) -> MemoryRecord | None:
        """Compatibility API: get latest record by key, scope, and optional agent."""

    @abstractmethod
    async def get_by_id(self, record_id: UUID) -> MemoryRecord | None:
        """Get one memory record by id."""

    @abstractmethod
    async def query(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        """Retrieve records by namespace and isolation filters."""

    @abstractmethod
    async def search(
        self,
        scope: MemoryScope,
        agent_name: str | None = None,
        workflow_id: UUID | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """Compatibility API: search records by isolation scope."""


class InMemoryMemoryRepository(MemoryRepository):
    """Process-local memory repository.

    This implementation is deterministic and dependency-free. It is intended
    for tests, local development, and as a contract reference for future Redis,
    PostgreSQL, and vector database adapters.
    """

    def __init__(self) -> None:
        self._records: dict[UUID, MemoryRecord] = {}

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        now = datetime.now(timezone.utc)
        stored = record.model_copy(update={"updated_at": now})
        self._records[stored.id] = stored
        return stored

    async def get(
        self,
        key: str,
        scope: MemoryScope,
        agent_name: str | None = None,
    ) -> MemoryRecord | None:
        matches = await self.query(
            MemoryQuery(
                key=key,
                scope=scope,
                agent_name=agent_name,
            )
        )
        if not matches:
            return None
        return max(matches, key=lambda record: record.updated_at)

    async def get_by_id(self, record_id: UUID) -> MemoryRecord | None:
        return self._records.get(record_id)

    async def query(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        records = [
            record
            for record in self._records.values()
            if self._matches(record, query)
        ]
        ordered = tuple(sorted(records, key=lambda record: record.updated_at))
        if query.limit is None:
            return ordered
        return ordered[-query.limit :]

    async def search(
        self,
        scope: MemoryScope,
        agent_name: str | None = None,
        workflow_id: UUID | None = None,
    ) -> tuple[MemoryRecord, ...]:
        return await self.query(
            MemoryQuery(
                scope=scope,
                agent_name=agent_name,
                workflow_id=workflow_id,
            )
        )

    def _matches(self, record: MemoryRecord, query: MemoryQuery) -> bool:
        return (
            (query.namespace is None or record.namespace == query.namespace)
            and (query.scope is None or record.scope == query.scope)
            and (query.key is None or record.key == query.key)
            and (query.agent_name is None or record.agent_name == query.agent_name)
            and (query.workflow_id is None or record.workflow_id == query.workflow_id)
            and (query.thread_id is None or record.thread_id == query.thread_id)
            and (query.record_type is None or record.record_type == query.record_type)
            and all(tag in record.tags for tag in query.tags)
        )


class NamespacedMemoryRepository:
    """Repository facade bound to a namespace."""

    def __init__(
        self,
        repository: MemoryRepository,
        namespace: MemoryNamespace,
    ) -> None:
        self._repository = repository
        self._namespace = namespace

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        return await self._repository.put(record.model_copy(update={"namespace": self._namespace}))

    async def query(self, query: MemoryQuery | None = None) -> tuple[MemoryRecord, ...]:
        base_query = query or MemoryQuery()
        return await self._repository.query(
            base_query.model_copy(update={"namespace": self._namespace})
        )
