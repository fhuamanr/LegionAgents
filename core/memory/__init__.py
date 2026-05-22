"""Shared memory system for the multi-agent platform."""

from core.memory.adr import ADRMemory
from core.memory.bugs import BugMemory
from core.memory.checkpoints import CheckpointMemory
from core.memory.history import ExecutionHistoryMemory
from core.memory.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from core.memory.intelligence import MemoryIntelligenceSystem
from core.memory.long_term import LongTermMemory
from core.memory.qdrant import QdrantAsyncClientProtocol, QdrantSemanticVectorStore, QdrantVectorStoreConfig
from core.memory.retrieval import MemoryRetrievalEngine
from core.memory.repository import (
    InMemoryMemoryRepository,
    MemoryRepository,
    NamespacedMemoryRepository,
)
from core.memory.semantic_index import SemanticMemoryIndexer
from core.memory.short_term import ShortTermMemory
from core.memory.vector_store import InMemorySemanticVectorStore, SemanticVectorStore
from core.memory.system import MemorySystem
from core.memory.vector import (
    InMemoryVectorMemoryRepository,
    VectorMemory,
    VectorMemoryRepository,
)

__all__ = [
    "ADRMemory",
    "BugMemory",
    "CheckpointMemory",
    "EmbeddingProvider",
    "ExecutionHistoryMemory",
    "HashingEmbeddingProvider",
    "InMemoryMemoryRepository",
    "InMemorySemanticVectorStore",
    "InMemoryVectorMemoryRepository",
    "LongTermMemory",
    "MemoryIntelligenceSystem",
    "MemoryRepository",
    "MemoryRetrievalEngine",
    "MemorySystem",
    "NamespacedMemoryRepository",
    "QdrantAsyncClientProtocol",
    "QdrantSemanticVectorStore",
    "QdrantVectorStoreConfig",
    "SemanticMemoryIndexer",
    "SemanticVectorStore",
    "ShortTermMemory",
    "VectorMemory",
    "VectorMemoryRepository",
]
