"""Approval persistence abstractions."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from core.contracts.approvals import (
    ApprovalQuery,
    ApprovalRecord,
    ApprovalStatus,
    WorkflowPause,
)


class ApprovalRepository(ABC):
    """Persistence boundary for approval workflow state."""

    @abstractmethod
    async def save(self, approval: ApprovalRecord) -> ApprovalRecord:
        """Save an approval record."""

    @abstractmethod
    async def get(self, approval_id: UUID) -> ApprovalRecord:
        """Get an approval record."""

    @abstractmethod
    async def list(self, query: ApprovalQuery | None = None) -> tuple[ApprovalRecord, ...]:
        """List approvals by query."""

    @abstractmethod
    async def save_pause(self, pause: WorkflowPause) -> WorkflowPause:
        """Persist workflow pause state."""

    @abstractmethod
    async def get_pause(self, workflow_id: UUID) -> WorkflowPause | None:
        """Get active workflow pause state."""

    @abstractmethod
    async def clear_pause(self, workflow_id: UUID) -> None:
        """Clear active workflow pause state."""


class InMemoryApprovalRepository(ApprovalRepository):
    """Local in-memory approval repository for development and tests."""

    def __init__(self) -> None:
        self._approvals: dict[UUID, ApprovalRecord] = {}
        self._pauses_by_workflow: dict[UUID, WorkflowPause] = {}

    async def save(self, approval: ApprovalRecord) -> ApprovalRecord:
        updated = approval.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._approvals[updated.id] = updated
        return updated

    async def get(self, approval_id: UUID) -> ApprovalRecord:
        return self._approvals[approval_id]

    async def list(self, query: ApprovalQuery | None = None) -> tuple[ApprovalRecord, ...]:
        approvals = tuple(sorted(self._approvals.values(), key=lambda approval: approval.created_at))
        if query is None:
            return approvals
        filtered: list[ApprovalRecord] = []
        for approval in approvals:
            if query.workflow_id and approval.workflow_id != query.workflow_id:
                continue
            if query.status and approval.status != query.status:
                continue
            if query.gate_type and approval.gate_type != query.gate_type:
                continue
            if query.reviewer_id and not any(
                reviewer.reviewer_id == query.reviewer_id for reviewer in approval.required_reviewers
            ):
                continue
            filtered.append(approval)
        return tuple(filtered)

    async def save_pause(self, pause: WorkflowPause) -> WorkflowPause:
        self._pauses_by_workflow[pause.workflow_id] = pause
        return pause

    async def get_pause(self, workflow_id: UUID) -> WorkflowPause | None:
        return self._pauses_by_workflow.get(workflow_id)

    async def clear_pause(self, workflow_id: UUID) -> None:
        self._pauses_by_workflow.pop(workflow_id, None)
