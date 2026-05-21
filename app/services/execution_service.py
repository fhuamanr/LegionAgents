"""Execution application service."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.schemas import (
    ExecutionLogResponse,
    ExecutionStatusResponse,
    ReportResponse,
    StoredUpload,
    TriggerWorkflowRequest,
    UploadResponse,
    UserStoryUploadRequest,
    WorkflowResponse,
    WorkflowStatus,
)
from core.streaming import (
    ExecutionEventEmitter,
    ExecutionEventType,
    ExecutionTracker,
    InMemoryExecutionEventBus,
    TimelineGenerator,
)


class ExecutionService:
    """In-memory application service for workflow and execution APIs."""

    def __init__(self, event_bus: InMemoryExecutionEventBus | None = None) -> None:
        self.event_bus = event_bus or InMemoryExecutionEventBus()
        self.emitter = ExecutionEventEmitter(self.event_bus)
        self.tracker = ExecutionTracker(self.event_bus)
        self.timeline = TimelineGenerator(self.event_bus)
        self._uploads: dict[UUID, StoredUpload] = {}
        self._workflows: dict[UUID, WorkflowResponse] = {}
        self._agent_statuses: dict[str, WorkflowStatus] = {
            "ba": WorkflowStatus.PENDING,
            "architect": WorkflowStatus.PENDING,
            "developer": WorkflowStatus.PENDING,
            "qa": WorkflowStatus.PENDING,
            "docs": WorkflowStatus.PENDING,
            "pr": WorkflowStatus.PENDING,
        }

    async def upload_user_story(self, request: UserStoryUploadRequest) -> UploadResponse:
        upload = StoredUpload(
            title=request.title,
            content=request.content,
            metadata=request.metadata,
        )
        self._uploads[upload.upload_id] = upload
        return UploadResponse(
            upload_id=upload.upload_id,
            title=upload.title,
            received_at=upload.received_at,
        )

    async def trigger_workflow(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
        now = datetime.now(timezone.utc)
        workflow_id = uuid4()
        metadata: dict[str, Any] = dict(request.metadata)
        if request.upload_id:
            metadata["upload_id"] = str(request.upload_id)
        workflow = WorkflowResponse(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            task=request.task,
            thread_id=request.thread_id,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )
        self._workflows[workflow_id] = workflow
        await self.tracker.start_workflow(workflow_id=workflow_id, total_steps=6)
        event = await self.emitter.emit(
            ExecutionEventType.AGENT_STARTED,
            workflow_id=workflow_id,
            thread_id=request.thread_id,
            agent_name="ba",
            message="Workflow triggered. BA agent is ready to start.",
            payload={"task": request.task},
        )
        await self.tracker.apply_event(event)
        self._agent_statuses["ba"] = WorkflowStatus.RUNNING
        return workflow

    async def get_workflow(self, workflow_id: UUID) -> WorkflowResponse:
        return self._workflows[workflow_id]

    async def get_execution_status(self, workflow_id: UUID) -> ExecutionStatusResponse:
        workflow = self._workflows[workflow_id]
        progress = await self.tracker.get(workflow_id)
        return ExecutionStatusResponse(
            workflow_id=workflow_id,
            status=workflow.status,
            active_agent=progress.active_agent if progress else None,
            progress_percent=progress.percent if progress else 0.0,
            metadata=workflow.metadata,
        )

    async def get_logs(self, workflow_id: UUID) -> ExecutionLogResponse:
        events = await self.event_bus.history(workflow_id=workflow_id)
        return ExecutionLogResponse(
            workflow_id=workflow_id,
            events=tuple(event.model_dump(mode="json") for event in events),
        )

    async def get_agent_statuses(self) -> dict[str, WorkflowStatus]:
        return dict(self._agent_statuses)

    async def get_report(self, workflow_id: UUID, kind: str) -> ReportResponse:
        workflow = self._workflows[workflow_id]
        logs = await self.get_logs(workflow_id)
        return ReportResponse(
            workflow_id=workflow_id,
            kind=kind,
            content={
                "workflow_status": workflow.status.value,
                "task": workflow.task,
                "events": list(logs.events),
            },
        )

