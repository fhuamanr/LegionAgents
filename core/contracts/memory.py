"""Memory contracts for workflow, agent, and platform state."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata


class MemoryScope(StrEnum):
    """Supported memory isolation levels."""

    AGENT = "agent"
    WORKFLOW = "workflow"
    THREAD = "thread"
    GLOBAL = "global"


class MemoryNamespace(StrEnum):
    """Canonical memory namespaces."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EXECUTION_HISTORY = "execution_history"
    ADR = "adr"
    BUG = "bug"
    CHECKPOINT = "checkpoint"
    VECTOR = "vector"


class MemoryRecordType(StrEnum):
    """Typed memory record families."""

    GENERIC = "generic"
    MESSAGE = "message"
    DECISION = "decision"
    EXECUTION_EVENT = "execution_event"
    ADR = "adr"
    BUG = "bug"
    CHECKPOINT = "checkpoint"
    VECTOR_DOCUMENT = "vector_document"


class MemoryQuery(ContractBaseModel):
    """Query for scoped memory retrieval."""

    namespace: MemoryNamespace | None = None
    scope: MemoryScope | None = None
    key: str | None = None
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    record_type: MemoryRecordType | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    limit: int | None = Field(default=None, ge=1)


class MemoryRecord(ContractBaseModel):
    """A persisted memory item."""

    id: UUID = Field(default_factory=uuid4)
    namespace: MemoryNamespace = MemoryNamespace.SHORT_TERM
    scope: MemoryScope
    record_type: MemoryRecordType = MemoryRecordType.GENERIC
    key: str = Field(min_length=1)
    value: dict[str, Any]
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShortTermMemoryRecord(MemoryRecord):
    """Thread-aware short-term memory."""

    namespace: MemoryNamespace = MemoryNamespace.SHORT_TERM
    expires_at: datetime | None = None


class LongTermMemoryRecord(MemoryRecord):
    """Durable long-term memory."""

    namespace: MemoryNamespace = MemoryNamespace.LONG_TERM
    importance: float = Field(default=0.5, ge=0, le=1)


class ExecutionHistoryRecord(MemoryRecord):
    """Execution event history for an agent or workflow."""

    namespace: MemoryNamespace = MemoryNamespace.EXECUTION_HISTORY
    record_type: MemoryRecordType = MemoryRecordType.EXECUTION_EVENT
    event_name: str = Field(min_length=1)


class ADRMemoryRecord(MemoryRecord):
    """Architecture decision record memory."""

    namespace: MemoryNamespace = MemoryNamespace.ADR
    record_type: MemoryRecordType = MemoryRecordType.ADR
    title: str = Field(min_length=1)
    status: str = Field(default="proposed", min_length=1)


class BugMemoryRecord(MemoryRecord):
    """Bug memory for defects, regressions, and known issues."""

    namespace: MemoryNamespace = MemoryNamespace.BUG
    record_type: MemoryRecordType = MemoryRecordType.BUG
    title: str = Field(min_length=1)
    severity: str = Field(default="medium", min_length=1)
    status: str = Field(default="open", min_length=1)


class CheckpointMemoryRecord(MemoryRecord):
    """LangGraph checkpoint-compatible local memory record."""

    namespace: MemoryNamespace = MemoryNamespace.CHECKPOINT
    record_type: MemoryRecordType = MemoryRecordType.CHECKPOINT
    checkpoint_id: str = Field(min_length=1)
    parent_checkpoint_id: str | None = None


class VectorMemoryRecord(MemoryRecord):
    """Vector-ready memory document.

    Embeddings are optional so the local memory layer can be used before a
    vector database or embedding provider is introduced.
    """

    namespace: MemoryNamespace = MemoryNamespace.VECTOR
    record_type: MemoryRecordType = MemoryRecordType.VECTOR_DOCUMENT
    text: str = Field(min_length=1)
    embedding: tuple[float, ...] | None = None


class VectorMemoryQuery(ContractBaseModel):
    """Vector-ready retrieval query."""

    text: str = Field(min_length=1)
    namespace: MemoryNamespace = MemoryNamespace.VECTOR
    scope: MemoryScope | None = None
    agent_name: str | None = None
    workflow_id: UUID | None = None
    thread_id: str | None = None
    embedding: tuple[float, ...] | None = None
    limit: int = Field(default=5, ge=1)


class VectorSearchResult(ContractBaseModel):
    """Vector retrieval result."""

    record: VectorMemoryRecord
    score: float = Field(ge=0)
