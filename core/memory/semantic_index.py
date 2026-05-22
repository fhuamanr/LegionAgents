"""Semantic indexing layer for memory intelligence."""

from uuid import uuid4

from core.contracts.memory import MemoryRecord
from core.contracts.memory_intelligence import (
    SemanticIndexRequest,
    SemanticIndexingSummary,
    SemanticMemoryDocument,
    SemanticMemoryKind,
)
from core.memory.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from core.memory.vector_store import SemanticVectorStore


class SemanticMemoryIndexer:
    """Indexes agent, workflow, and organizational memory into a vector store."""

    def __init__(
        self,
        store: SemanticVectorStore,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self._store = store
        self._embeddings = embeddings or HashingEmbeddingProvider()

    async def index(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        embedding = await self._embeddings.embed(request.text)
        document = SemanticMemoryDocument(
            id=uuid4(),
            key=request.key,
            text=request.text,
            kind=request.kind,
            scope=request.scope,
            agent_name=request.agent_name,
            workflow_id=request.workflow_id,
            thread_id=request.thread_id,
            source_record_id=request.source_record_id,
            tags=request.tags,
            embedding=embedding,
            metadata=request.metadata,
        )
        return await self._store.upsert(document)

    async def index_records(
        self,
        records: tuple[MemoryRecord, ...],
        kind: SemanticMemoryKind,
    ) -> SemanticIndexingSummary:
        indexed_ids = []
        skipped = 0
        for record in records:
            text = self._record_text(record)
            if not text:
                skipped += 1
                continue
            document = await self.index(
                SemanticIndexRequest(
                    key=record.key,
                    text=text,
                    kind=kind,
                    scope=record.scope,
                    agent_name=record.agent_name,
                    workflow_id=record.workflow_id,
                    thread_id=record.thread_id,
                    source_record_id=record.id,
                    tags=record.tags,
                    metadata={"namespace": record.namespace.value, "record_type": record.record_type.value},
                )
            )
            indexed_ids.append(document.id)
        return SemanticIndexingSummary(
            indexed_count=len(indexed_ids),
            skipped_count=skipped,
            document_ids=tuple(indexed_ids),
        )

    def _record_text(self, record: MemoryRecord) -> str:
        text = record.value.get("text") or record.value.get("summary") or record.value.get("decision") or record.value.get("error")
        if isinstance(text, str):
            return text
        return " ".join(f"{key}: {value}" for key, value in record.value.items())
