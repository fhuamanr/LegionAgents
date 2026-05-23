"""Execution persistence for real LangGraph workflow runs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.states import WorkflowExecutionState
from core.persistence import PostgresJsonDocumentStore


class WorkflowRunStatus(StrEnum):
    """Lifecycle status for one executable workflow run."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowCheckpoint(BaseModel):
    """Recoverable snapshot captured during workflow execution."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    workflow_id: UUID
    sequence: int = Field(ge=0)
    status: WorkflowRunStatus
    active_agent: str | None = None
    next_agent: str | None = None
    state: WorkflowExecutionState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionRecord(BaseModel):
    """Persisted execution envelope for workflow recovery and auditing."""

    model_config = ConfigDict(frozen=True)

    execution_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    task: str = Field(min_length=1)
    status: WorkflowRunStatus = WorkflowRunStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    active_agent: str | None = None
    next_agent: str | None = None
    checkpoints: tuple[WorkflowCheckpoint, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionRepository(ABC):
    """Persistence boundary for executable workflows."""

    @abstractmethod
    async def create(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        """Persist a new execution record."""

    @abstractmethod
    async def get(self, execution_id: UUID) -> WorkflowExecutionRecord:
        """Return a persisted execution record."""

    @abstractmethod
    async def update(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        """Replace a persisted execution record."""

    @abstractmethod
    async def append_checkpoint(self, checkpoint: WorkflowCheckpoint) -> WorkflowExecutionRecord:
        """Append a checkpoint and return the updated execution record."""

    @abstractmethod
    async def latest_checkpoint(self, execution_id: UUID) -> WorkflowCheckpoint | None:
        """Return the newest checkpoint for an execution."""

    @abstractmethod
    async def cancel(self, execution_id: UUID, reason: str | None = None) -> WorkflowExecutionRecord:
        """Request workflow cancellation."""


class InMemoryWorkflowExecutionRepository(WorkflowExecutionRepository):
    """Thread-safe enough local persistence for tests and single-process runs."""

    def __init__(self) -> None:
        self._records: dict[UUID, WorkflowExecutionRecord] = {}

    async def create(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        stored = record.model_copy(deep=True)
        self._records[record.execution_id] = stored
        return stored

    async def get(self, execution_id: UUID) -> WorkflowExecutionRecord:
        return self._records[execution_id].model_copy(deep=True)

    async def update(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        updated = record.model_copy(
            update={"updated_at": datetime.now(timezone.utc)},
            deep=True,
        )
        self._records[record.execution_id] = updated
        return updated

    async def append_checkpoint(self, checkpoint: WorkflowCheckpoint) -> WorkflowExecutionRecord:
        record = self._records[checkpoint.execution_id]
        updated = record.model_copy(
            update={
                "status": checkpoint.status,
                "updated_at": checkpoint.created_at,
                "active_agent": checkpoint.active_agent,
                "next_agent": checkpoint.next_agent,
                "checkpoints": record.checkpoints + (checkpoint.model_copy(deep=True),),
                "metadata": {
                    **record.metadata,
                    "last_checkpoint_id": str(checkpoint.checkpoint_id),
                    "last_checkpoint_sequence": checkpoint.sequence,
                },
            }
        )
        self._records[checkpoint.execution_id] = updated
        return updated

    async def latest_checkpoint(self, execution_id: UUID) -> WorkflowCheckpoint | None:
        record = self._records[execution_id]
        if not record.checkpoints:
            return None
        return deepcopy(record.checkpoints[-1])

    async def cancel(self, execution_id: UUID, reason: str | None = None) -> WorkflowExecutionRecord:
        record = self._records[execution_id]
        now = datetime.now(timezone.utc)
        updated = record.model_copy(
            update={
                "status": WorkflowRunStatus.CANCELLED,
                "updated_at": now,
                "cancelled_at": now,
                "cancellation_reason": reason,
            }
        )
        self._records[execution_id] = updated
        return updated


class PostgresWorkflowExecutionRepository(WorkflowExecutionRepository):
    """PostgreSQL-backed workflow execution and checkpoint persistence."""

    _bucket = "workflow_executions"

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store

    async def create(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        await self._persist(record)
        return record

    async def get(self, execution_id: UUID) -> WorkflowExecutionRecord:
        return WorkflowExecutionRecord.model_validate(
            await self._store.get(bucket=self._bucket, document_id=execution_id)
        )

    async def update(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        updated = record.model_copy(
            update={"updated_at": datetime.now(timezone.utc)},
            deep=True,
        )
        await self._persist(updated)
        return updated

    async def append_checkpoint(self, checkpoint: WorkflowCheckpoint) -> WorkflowExecutionRecord:
        record = await self.get(checkpoint.execution_id)
        updated = record.model_copy(
            update={
                "status": checkpoint.status,
                "updated_at": checkpoint.created_at,
                "active_agent": checkpoint.active_agent,
                "next_agent": checkpoint.next_agent,
                "checkpoints": record.checkpoints + (checkpoint.model_copy(deep=True),),
                "metadata": {
                    **record.metadata,
                    "last_checkpoint_id": str(checkpoint.checkpoint_id),
                    "last_checkpoint_sequence": checkpoint.sequence,
                },
            }
        )
        await self._persist(updated)
        return updated

    async def latest_checkpoint(self, execution_id: UUID) -> WorkflowCheckpoint | None:
        record = await self.get(execution_id)
        if not record.checkpoints:
            return None
        return deepcopy(record.checkpoints[-1])

    async def cancel(self, execution_id: UUID, reason: str | None = None) -> WorkflowExecutionRecord:
        record = await self.get(execution_id)
        now = datetime.now(timezone.utc)
        updated = record.model_copy(
            update={
                "status": WorkflowRunStatus.CANCELLED,
                "updated_at": now,
                "cancelled_at": now,
                "cancellation_reason": reason,
            }
        )
        await self._persist(updated)
        return updated

    async def _persist(self, record: WorkflowExecutionRecord) -> None:
        await self._store.upsert(
            bucket=self._bucket,
            document_id=record.execution_id,
            key=f"{record.workflow_id}:{record.created_at.isoformat()}",
            payload=record.model_dump(mode="json"),
        )
