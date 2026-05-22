"""Qdrant-ready vector storage adapter boundary."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from core.contracts.memory_intelligence import (
    SemanticMemoryDocument,
    SemanticRetrievalQuery,
    SemanticRetrievalResult,
)
from core.memory.vector_store import SemanticVectorStore


@dataclass(frozen=True, slots=True)
class QdrantVectorStoreConfig:
    """Qdrant collection configuration."""

    url: str = "http://qdrant:6333"
    collection_name: str = "multi_agent_memory"
    vector_size: int = 64
    distance: str = "Cosine"


class QdrantAsyncClientProtocol(Protocol):
    """Minimal protocol expected from an async Qdrant client."""

    async def upsert(self, collection_name: str, points: Any) -> Any:
        """Upsert points into a collection."""

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        query_filter: Any | None = None,
    ) -> Any:
        """Search points in a collection."""


class QdrantSemanticVectorStore(SemanticVectorStore):
    """Qdrant adapter boundary.

    The adapter accepts an injected async client to avoid hard-coding a client
    dependency in core. Production wiring can pass `qdrant-client` here.
    """

    def __init__(
        self,
        config: QdrantVectorStoreConfig | None = None,
        client: QdrantAsyncClientProtocol | None = None,
    ) -> None:
        self._config = config or QdrantVectorStoreConfig()
        self._client = client

    async def upsert(self, document: SemanticMemoryDocument) -> SemanticMemoryDocument:
        if self._client is None:
            raise NotImplementedError("Qdrant client is not configured")
        await self._client.upsert(
            collection_name=self._config.collection_name,
            points=[
                {
                    "id": str(document.id),
                    "vector": list(document.embedding or tuple()),
                    "payload": self._payload(document),
                }
            ],
        )
        return document

    async def search(
        self,
        query: SemanticRetrievalQuery,
        embedding: tuple[float, ...],
    ) -> tuple[SemanticRetrievalResult, ...]:
        if self._client is None:
            raise NotImplementedError("Qdrant client is not configured")
        hits = await self._client.search(
            collection_name=self._config.collection_name,
            query_vector=list(embedding),
            limit=query.limit,
            query_filter=self._filter(query),
        )
        return tuple(self._result_from_hit(hit) for hit in hits)

    def _payload(self, document: SemanticMemoryDocument) -> dict[str, Any]:
        return {
            "key": document.key,
            "text": document.text,
            "kind": document.kind.value,
            "scope": document.scope.value,
            "agent_name": document.agent_name,
            "workflow_id": str(document.workflow_id) if document.workflow_id else None,
            "thread_id": document.thread_id,
            "source_record_id": str(document.source_record_id) if document.source_record_id else None,
            "tags": list(document.tags),
            "metadata": document.metadata,
        }

    def _filter(self, query: SemanticRetrievalQuery) -> dict[str, Any]:
        must: list[dict[str, Any]] = []
        if query.scope:
            must.append({"key": "scope", "match": {"value": query.scope.value}})
        if query.agent_name:
            must.append({"key": "agent_name", "match": {"value": query.agent_name}})
        if query.workflow_id:
            must.append({"key": "workflow_id", "match": {"value": str(query.workflow_id)}})
        if query.thread_id:
            must.append({"key": "thread_id", "match": {"value": query.thread_id}})
        if query.kinds:
            must.append({"key": "kind", "match": {"any": [kind.value for kind in query.kinds]}})
        return {"must": must} if must else {}

    def _result_from_hit(self, hit: Any) -> SemanticRetrievalResult:
        payload = self._hit_payload(hit)
        document = SemanticMemoryDocument(
            id=UUID(str(getattr(hit, "id", payload.get("id")))),
            key=str(payload.get("key", "qdrant-memory")),
            text=str(payload.get("text", "")),
            kind=payload.get("kind", "generic"),
            scope=payload.get("scope", "global"),
            agent_name=payload.get("agent_name"),
            workflow_id=UUID(str(payload["workflow_id"])) if payload.get("workflow_id") else None,
            thread_id=payload.get("thread_id"),
            source_record_id=UUID(str(payload["source_record_id"])) if payload.get("source_record_id") else None,
            tags=tuple(payload.get("tags", tuple())),
            metadata=dict(payload.get("metadata", {})),
        )
        score = float(getattr(hit, "score", payload.get("score", 0.0)))
        return SemanticRetrievalResult(document=document, score=max(0.0, min(1.0, score)), reasons=("qdrant_vector_match",))

    def _hit_payload(self, hit: Any) -> dict[str, Any]:
        payload = getattr(hit, "payload", None)
        if isinstance(payload, dict):
            return payload
        if isinstance(hit, dict):
            hit_payload = hit.get("payload", {})
            return hit_payload if isinstance(hit_payload, dict) else {}
        return {}
