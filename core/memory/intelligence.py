"""Composed multi-agent memory intelligence system."""

from core.contracts.memory import MemoryQuery
from core.contracts.memory_intelligence import (
    SemanticIndexRequest,
    SemanticIndexingSummary,
    SemanticMemoryDocument,
    SemanticMemoryKind,
    SemanticRetrievalQuery,
    SemanticRetrievalResult,
)
from core.memory.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from core.memory.repository import MemoryRepository
from core.memory.retrieval import MemoryRetrievalEngine
from core.memory.semantic_index import SemanticMemoryIndexer
from core.memory.vector_store import InMemorySemanticVectorStore, SemanticVectorStore


class MemoryIntelligenceSystem:
    """High-level semantic memory, learning, and retrieval facade."""

    def __init__(
        self,
        repository: MemoryRepository | None = None,
        store: SemanticVectorStore | None = None,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self._repository = repository
        self.store = store or InMemorySemanticVectorStore()
        self.embeddings = embeddings or HashingEmbeddingProvider()
        self.indexer = SemanticMemoryIndexer(self.store, self.embeddings)
        self.retrieval = MemoryRetrievalEngine(self.store, self.embeddings)

    async def index(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        return await self.indexer.index(request)

    async def retrieve(self, query: SemanticRetrievalQuery) -> tuple[SemanticRetrievalResult, ...]:
        return await self.retrieval.retrieve(query)

    async def index_execution_history(self, query: MemoryQuery | None = None) -> SemanticIndexingSummary:
        if self._repository is None:
            raise ValueError("Memory repository is required for execution history indexing")
        records = await self._repository.query(query or MemoryQuery())
        return await self.indexer.index_records(records, SemanticMemoryKind.EXECUTION_HISTORY)

    async def learn_historical_bug(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        return await self.index(request.model_copy(update={"kind": SemanticMemoryKind.HISTORICAL_BUG}))

    async def learn_architectural_decision(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        return await self.index(request.model_copy(update={"kind": SemanticMemoryKind.ARCHITECTURAL_DECISION}))

    async def learn_coding_pattern(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        return await self.index(request.model_copy(update={"kind": SemanticMemoryKind.CODING_PATTERN}))

    async def learn_qa_outcome(self, request: SemanticIndexRequest) -> SemanticMemoryDocument:
        return await self.index(request.model_copy(update={"kind": SemanticMemoryKind.QA_LEARNING}))
