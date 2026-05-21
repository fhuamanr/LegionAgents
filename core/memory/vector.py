"""Vector-ready memory interfaces and local implementation."""

from abc import ABC, abstractmethod
from math import sqrt
from typing import Any
from uuid import UUID

from core.contracts.memory import (
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
    VectorMemoryQuery,
    VectorMemoryRecord,
    VectorSearchResult,
)
from core.memory.repository import MemoryRepository


class VectorMemoryRepository(ABC):
    """Vector-ready repository boundary for future vector databases."""

    @abstractmethod
    async def upsert(self, record: VectorMemoryRecord) -> VectorMemoryRecord:
        """Insert or update a vector memory document."""

    @abstractmethod
    async def search(self, query: VectorMemoryQuery) -> tuple[VectorSearchResult, ...]:
        """Search vector memory."""


class InMemoryVectorMemoryRepository(VectorMemoryRepository):
    """Local vector-ready repository.

    If embeddings are provided, cosine similarity is used. Otherwise retrieval
    falls back to deterministic case-insensitive text containment scoring.
    """

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def upsert(self, record: VectorMemoryRecord) -> VectorMemoryRecord:
        stored = await self._repository.put(record)
        return VectorMemoryRecord.model_validate(stored)

    async def search(self, query: VectorMemoryQuery) -> tuple[VectorSearchResult, ...]:
        records = await self._repository.query(
            MemoryQuery(
                namespace=MemoryNamespace.VECTOR,
                scope=query.scope,
                agent_name=query.agent_name,
                workflow_id=query.workflow_id,
                thread_id=query.thread_id,
            )
        )
        vector_records = tuple(VectorMemoryRecord.model_validate(record) for record in records)
        scored = [
            VectorSearchResult(record=record, score=self._score(record, query))
            for record in vector_records
        ]
        ranked = sorted(scored, key=lambda item: item.score, reverse=True)
        return tuple(result for result in ranked[: query.limit] if result.score > 0)

    def _score(self, record: VectorMemoryRecord, query: VectorMemoryQuery) -> float:
        if record.embedding and query.embedding:
            return self._cosine(record.embedding, query.embedding)
        text = record.text.lower()
        query_text = query.text.lower()
        if query_text in text:
            return 1.0
        terms = [term for term in query_text.split() if term]
        if not terms:
            return 0.0
        matches = sum(1 for term in terms if term in text)
        return matches / len(terms)

    def _cosine(self, left: tuple[float, ...], right: tuple[float, ...]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, dot / (left_norm * right_norm))


class VectorMemory:
    """High-level vector-ready memory service."""

    def __init__(self, repository: VectorMemoryRepository) -> None:
        self._repository = repository

    async def remember(
        self,
        key: str,
        text: str,
        value: dict[str, Any],
        scope: MemoryScope,
        agent_name: str | None = None,
        workflow_id: UUID | None = None,
        thread_id: str | None = None,
        embedding: tuple[float, ...] | None = None,
        tags: tuple[str, ...] = tuple(),
    ) -> VectorMemoryRecord:
        return await self._repository.upsert(
            VectorMemoryRecord(
                scope=scope,
                key=key,
                value=value,
                text=text,
                agent_name=agent_name,
                workflow_id=workflow_id,
                thread_id=thread_id,
                embedding=embedding,
                tags=tags,
            )
        )

    async def search(self, query: VectorMemoryQuery) -> tuple[VectorSearchResult, ...]:
        return await self._repository.search(query)

