"""Vector storage abstractions for semantic memory intelligence."""

from abc import ABC, abstractmethod
from math import sqrt

from core.contracts.memory import MemoryScope
from core.contracts.memory_intelligence import (
    SemanticMemoryDocument,
    SemanticRetrievalQuery,
    SemanticRetrievalResult,
)


class SemanticVectorStore(ABC):
    """Vector database boundary for semantic memory documents."""

    @abstractmethod
    async def upsert(self, document: SemanticMemoryDocument) -> SemanticMemoryDocument:
        """Insert or update a semantic document."""

    @abstractmethod
    async def search(
        self,
        query: SemanticRetrievalQuery,
        embedding: tuple[float, ...],
    ) -> tuple[SemanticRetrievalResult, ...]:
        """Search semantic documents by embedding and metadata filters."""


class InMemorySemanticVectorStore(SemanticVectorStore):
    """Local vector store used for tests and local development."""

    def __init__(self) -> None:
        self._documents: dict[str, SemanticMemoryDocument] = {}

    async def upsert(self, document: SemanticMemoryDocument) -> SemanticMemoryDocument:
        self._documents[str(document.id)] = document
        return document

    async def search(
        self,
        query: SemanticRetrievalQuery,
        embedding: tuple[float, ...],
    ) -> tuple[SemanticRetrievalResult, ...]:
        results = [
            SemanticRetrievalResult(
                document=document,
                score=self._cosine(document.embedding or tuple(), embedding),
                reasons=self._reasons(document, query),
            )
            for document in self._documents.values()
            if self._matches(document, query)
        ]
        ranked = sorted(results, key=lambda result: result.score, reverse=True)
        return tuple(result for result in ranked[: query.limit] if result.score >= query.min_score)

    def _matches(self, document: SemanticMemoryDocument, query: SemanticRetrievalQuery) -> bool:
        allowed_by_scope = query.scope is None or document.scope == query.scope
        allowed_by_agent = query.agent_name is None or document.agent_name == query.agent_name
        if query.include_shared and query.agent_name is not None:
            allowed_by_agent = allowed_by_agent or document.scope == MemoryScope.GLOBAL
        return (
            allowed_by_scope
            and allowed_by_agent
            and (query.workflow_id is None or document.workflow_id == query.workflow_id)
            and (query.thread_id is None or document.thread_id == query.thread_id)
            and (not query.kinds or document.kind in query.kinds)
            and all(tag in document.tags for tag in query.tags)
        )

    def _reasons(self, document: SemanticMemoryDocument, query: SemanticRetrievalQuery) -> tuple[str, ...]:
        reasons: list[str] = []
        if query.agent_name and document.agent_name == query.agent_name:
            reasons.append("agent_specific_match")
        if document.scope == MemoryScope.GLOBAL:
            reasons.append("shared_organizational_memory")
        if query.kinds and document.kind in query.kinds:
            reasons.append(f"kind:{document.kind.value}")
        return tuple(reasons)

    def _cosine(self, left: tuple[float, ...], right: tuple[float, ...]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (left_norm * right_norm)))
