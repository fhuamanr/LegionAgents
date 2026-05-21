"""Execution progress tracking."""

from uuid import UUID

from core.streaming.bus import ExecutionEventBus
from core.streaming.emitter import ExecutionEventEmitter
from core.streaming.models import ExecutionEvent, ExecutionEventType, ExecutionProgress


class ExecutionTracker:
    """Tracks workflow progress from structured events."""

    def __init__(self, event_bus: ExecutionEventBus) -> None:
        self._event_bus = event_bus
        self._emitter = ExecutionEventEmitter(event_bus)
        self._progress: dict[UUID, ExecutionProgress] = {}

    async def start_workflow(self, workflow_id: UUID, total_steps: int) -> ExecutionProgress:
        progress = ExecutionProgress(workflow_id=workflow_id, total_steps=total_steps)
        self._progress[workflow_id] = progress
        await self._emit_progress(progress)
        return progress

    async def apply_event(self, event: ExecutionEvent) -> ExecutionProgress | None:
        if event.workflow_id is None:
            return None
        progress = self._progress.get(event.workflow_id) or ExecutionProgress(
            workflow_id=event.workflow_id
        )

        if event.type == ExecutionEventType.AGENT_STARTED:
            progress = progress.model_copy(update={"active_agent": event.agent_name})
        elif event.type in {
            ExecutionEventType.AGENT_COMPLETED,
            ExecutionEventType.PR_GENERATED,
            ExecutionEventType.DOCS_GENERATED,
        }:
            progress = progress.model_copy(
                update={
                    "completed_steps": progress.completed_steps + 1,
                    "active_agent": event.agent_name,
                }
            )
        elif event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}:
            progress = progress.model_copy(update={"failed": True, "active_agent": event.agent_name})

        self._progress[event.workflow_id] = progress
        await self._emit_progress(progress)
        return progress

    async def get(self, workflow_id: UUID) -> ExecutionProgress | None:
        return self._progress.get(workflow_id)

    async def _emit_progress(self, progress: ExecutionProgress) -> None:
        await self._emitter.emit(
            ExecutionEventType.PROGRESS_UPDATED,
            workflow_id=progress.workflow_id,
            agent_name=progress.active_agent,
            message="Execution progress updated.",
            payload=progress.model_dump(mode="json"),
        )

