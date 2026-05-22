"""Semantic memory retrieval engine."""

from core.contracts.memory_intelligence import SemanticRetrievalQuery, SemanticRetrievalResult
from core.memory.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from core.memory.vector_store import SemanticVectorStore


class MemoryRetrievalEngine:
    """Retrieves agent-specific and shared organizational memory semantically."""

    def __init__(
        self,
        store: SemanticVectorStore,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self._store = store
        self._embeddings = embeddings or HashingEmbeddingProvider()

    async def retrieve(self, query: SemanticRetrievalQuery) -> tuple[SemanticRetrievalResult, ...]:
        embedding = await self._embeddings.embed(query.text)
        return await self._store.search(query, embedding)
