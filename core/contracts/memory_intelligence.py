"""Contracts for semantic multi-agent memory intelligence."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata
from core.contracts.memory import MemoryScope


class SemanticMemoryKind(StrEnum):
    """Semantic memory families used by retrieval and learning systems."""

    GENERIC = "generic"
    HISTORICAL_BUG = "historical_bug"
    ARCHITECTURAL_DECISION = "architectural_decision"
    CODING_PATTERN = "coding_pattern"
    QA_LEARNING = "qa_learning"
    EXECUTION_HISTORY = "execution_history"


class SemanticMemoryDocument(ContractBaseModel):
    """Indexable semantic memory document."""

    id: UUID
    key: str
    text: str = Field(min_length=1)
    kind: SemanticMemoryKind = SemanticMemoryKind.GENERIC
    scope: MemoryScope = MemoryScope.GLOBAL
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    source_record_id: UUID | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    embedding: tuple[float, ...] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)


class SemanticIndexRequest(ContractBaseModel):
    """Request to index a semantic memory document."""

    key: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: SemanticMemoryKind = SemanticMemoryKind.GENERIC
    scope: MemoryScope = MemoryScope.GLOBAL
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    source_record_id: UUID | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticRetrievalQuery(ContractBaseModel):
    """Semantic retrieval query across agent and organizational memory."""

    text: str = Field(min_length=1)
    kinds: tuple[SemanticMemoryKind, ...] = Field(default_factory=tuple)
    scope: MemoryScope | None = None
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    include_shared: bool = True
    tags: tuple[str, ...] = Field(default_factory=tuple)
    limit: int = Field(default=5, ge=1)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SemanticRetrievalResult(ContractBaseModel):
    """Semantic retrieval result with ranking metadata."""

    document: SemanticMemoryDocument
    score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = Field(default_factory=tuple)


class SemanticIndexingSummary(ContractBaseModel):
    """Indexing summary for execution history and memory batches."""

    indexed_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    document_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
