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
    WorkflowTelemetryEdge,
    WorkflowTelemetryNode,
    WorkflowTelemetryResponse,
    WorkflowTelemetryTimelineItem,
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
from core.graph import (
    InMemoryWorkflowExecutionRepository,
    LangGraphExecutionRuntime,
    WorkflowRunStatus,
)


class ExecutionService:
    """In-memory application service for workflow and execution APIs."""

    def __init__(self, event_bus: InMemoryExecutionEventBus | None = None) -> None:
        self.event_bus = event_bus or InMemoryExecutionEventBus()
        self.emitter = ExecutionEventEmitter(self.event_bus)
        self.tracker = ExecutionTracker(self.event_bus)
        self.timeline = TimelineGenerator(self.event_bus)
        self.workflow_repository = InMemoryWorkflowExecutionRepository()
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
        self._agent_labels: dict[str, str] = {
            "ba": "BA",
            "architect": "Architect",
            "developer": "Developer",
            "qa": "QA",
            "docs": "Docs",
            "pr": "PR",
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
        runtime = LangGraphExecutionRuntime(
            repository=self.workflow_repository,
            event_hook=self._runtime_event_hook(workflow_id, request.thread_id),
        )
        result = await runtime.start(
            request.task,
            workflow_id=workflow_id,
            metadata=metadata,
        )
        final_workflow = workflow.model_copy(
            update={
                "status": self._workflow_status_from_run(result.status),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {
                    **metadata,
                    "execution_id": str(result.execution_id),
                    "checkpoint_count": len(result.checkpoints),
                    "runtime_status": result.status.value,
                },
            }
        )
        self._workflows[workflow_id] = final_workflow
        return final_workflow

    async def get_workflow(self, workflow_id: UUID) -> WorkflowResponse:
        return self._workflows[workflow_id]

    async def pause_workflow(self, workflow_id: UUID, metadata: dict[str, Any]) -> WorkflowResponse:
        """Mark a workflow as paused."""

        workflow = self._workflows[workflow_id]
        updated = workflow.model_copy(
            update={
                "status": WorkflowStatus.PAUSED,
                "updated_at": datetime.now(timezone.utc),
                "metadata": {**workflow.metadata, **metadata},
            }
        )
        self._workflows[workflow_id] = updated
        return updated

    async def resume_workflow(self, workflow_id: UUID, metadata: dict[str, Any]) -> WorkflowResponse:
        """Mark a workflow as running after approval."""

        workflow = self._workflows[workflow_id]
        updated = workflow.model_copy(
            update={
                "status": WorkflowStatus.RUNNING,
                "updated_at": datetime.now(timezone.utc),
                "metadata": {**workflow.metadata, **metadata},
            }
        )
        self._workflows[workflow_id] = updated
        return updated

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

    async def get_workflow_telemetry(self, workflow_id: UUID) -> WorkflowTelemetryResponse:
        """Build a live visualization snapshot for a workflow."""

        workflow = self._workflows[workflow_id]
        events = await self.event_bus.history(workflow_id=workflow_id)
        progress = await self.tracker.get(workflow_id)
        now = datetime.now(timezone.utc)
        nodes = self._telemetry_nodes(events, now)
        return WorkflowTelemetryResponse(
            workflow_id=workflow_id,
            status=workflow.status,
            active_agent=progress.active_agent if progress else None,
            progress_percent=progress.percent if progress else 0.0,
            duration_ms=self._duration_ms(workflow.created_at, now),
            nodes=nodes,
            edges=self._telemetry_edges(),
            timeline=self._telemetry_timeline(events),
            mermaid=self._telemetry_mermaid(nodes),
            metadata={
                "event_count": len(events),
                "retry_count": sum(1 for event in events if event.type == ExecutionEventType.RETRY_STARTED),
                "qa_loop_count": sum(1 for event in events if event.type == ExecutionEventType.QA_FAILED),
                "websocket_channel": f"/ws/executions/{workflow_id}",
            },
        )

    async def get_agent_statuses(self) -> dict[str, WorkflowStatus]:
        return dict(self._agent_statuses)

    async def get_report(self, workflow_id: UUID, kind: str) -> ReportResponse:
        workflow = self._workflows[workflow_id]
        logs = await self.get_logs(workflow_id)
        execution_id = workflow.metadata.get("execution_id")
        latest_state: dict[str, Any] | None = None
        if execution_id:
            checkpoint = await self.workflow_repository.latest_checkpoint(UUID(str(execution_id)))
            latest_state = checkpoint.state.model_dump(mode="json") if checkpoint else None
        return ReportResponse(
            workflow_id=workflow_id,
            kind=kind,
            content={
                "workflow_status": workflow.status.value,
                "task": workflow.task,
                "events": list(logs.events),
                "latest_state": latest_state,
            },
        )

    def _runtime_event_hook(self, workflow_id: UUID, thread_id: str | None):
        async def emit_runtime_event(event_name: str, state: dict[str, Any]) -> None:
            agent_name = str(state.get("next_agent") or state.get("last_agent") or "")
            event_type = self._runtime_event_type(event_name, agent_name)
            event = await self.emitter.emit(
                event_type,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name or None,
                message=self._runtime_event_message(event_name, agent_name),
                payload={
                    "attempts": state.get("attempts", {}),
                    "status": state.get("status"),
                },
            )
            await self.tracker.apply_event(event)
            if agent_name in self._agent_statuses:
                self._agent_statuses[agent_name] = self._agent_status_from_event(event_type)

        return emit_runtime_event

    def _runtime_event_type(self, event_name: str, agent_name: str) -> ExecutionEventType:
        if event_name == "retry_started":
            return ExecutionEventType.RETRY_STARTED
        if event_name == "agent_failed":
            return ExecutionEventType.QA_FAILED if agent_name == "qa" else ExecutionEventType.AGENT_FAILED
        if event_name == "agent_completed":
            if agent_name == "docs":
                return ExecutionEventType.DOCS_GENERATED
            if agent_name == "pr":
                return ExecutionEventType.PR_GENERATED
            return ExecutionEventType.AGENT_COMPLETED
        return ExecutionEventType.AGENT_STARTED

    def _runtime_event_message(self, event_name: str, agent_name: str) -> str:
        labels = self._agent_labels
        label = labels.get(agent_name, agent_name or "Workflow")
        if event_name == "retry_started":
            return f"{label} retry started."
        if event_name == "agent_failed":
            return f"{label} agent failed."
        if event_name == "agent_completed":
            return f"{label} agent completed."
        return f"{label} agent started."

    def _agent_status_from_event(self, event_type: ExecutionEventType) -> WorkflowStatus:
        if event_type == ExecutionEventType.AGENT_STARTED or event_type == ExecutionEventType.RETRY_STARTED:
            return WorkflowStatus.RUNNING
        if event_type in {
            ExecutionEventType.AGENT_COMPLETED,
            ExecutionEventType.DOCS_GENERATED,
            ExecutionEventType.PR_GENERATED,
        }:
            return WorkflowStatus.COMPLETED
        return WorkflowStatus.FAILED

    def _workflow_status_from_run(self, status: WorkflowRunStatus) -> WorkflowStatus:
        if status == WorkflowRunStatus.COMPLETED:
            return WorkflowStatus.COMPLETED
        if status == WorkflowRunStatus.PAUSED:
            return WorkflowStatus.PAUSED
        if status == WorkflowRunStatus.CANCELLED:
            return WorkflowStatus.CANCELLED
        if status == WorkflowRunStatus.RUNNING:
            return WorkflowStatus.RUNNING
        return WorkflowStatus.FAILED

    def _telemetry_nodes(
        self,
        events: tuple[Any, ...],
        now: datetime,
    ) -> tuple[WorkflowTelemetryNode, ...]:
        statuses = {agent: WorkflowStatus.PENDING for agent in self._agent_labels}
        started_at: dict[str, datetime] = {}
        completed_at: dict[str, datetime] = {}
        retry_counts = {agent: 0 for agent in self._agent_labels}

        for event in events:
            if not event.agent_name or event.agent_name not in statuses:
                continue
            if event.type == ExecutionEventType.AGENT_STARTED:
                statuses[event.agent_name] = WorkflowStatus.RUNNING
                started_at.setdefault(event.agent_name, event.timestamp)
            elif event.type in {
                ExecutionEventType.AGENT_COMPLETED,
                ExecutionEventType.DOCS_GENERATED,
                ExecutionEventType.PR_GENERATED,
            }:
                statuses[event.agent_name] = WorkflowStatus.COMPLETED
                completed_at[event.agent_name] = event.timestamp
            elif event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}:
                statuses[event.agent_name] = WorkflowStatus.FAILED
                completed_at[event.agent_name] = event.timestamp
            elif event.type == ExecutionEventType.RETRY_STARTED:
                statuses[event.agent_name] = WorkflowStatus.RUNNING
                retry_counts[event.agent_name] += 1

        return tuple(
            WorkflowTelemetryNode(
                id=agent,
                label=label,
                agent_name=agent,
                status=statuses[agent],
                started_at=started_at.get(agent),
                completed_at=completed_at.get(agent),
                duration_ms=self._duration_ms(started_at[agent], completed_at.get(agent, now)) if agent in started_at else None,
                retry_count=retry_counts[agent],
                metadata={"dependency_index": index},
            )
            for index, (agent, label) in enumerate(self._agent_labels.items())
        )

    def _telemetry_edges(self) -> tuple[WorkflowTelemetryEdge, ...]:
        return (
            WorkflowTelemetryEdge(source="ba", target="architect", label="requirements"),
            WorkflowTelemetryEdge(source="architect", target="developer", label="architecture"),
            WorkflowTelemetryEdge(source="developer", target="qa", label="implementation"),
            WorkflowTelemetryEdge(source="qa", target="docs", label="approved", condition="qa_passed"),
            WorkflowTelemetryEdge(source="qa", target="developer", label="rejected", condition="qa_failed", is_loop=True),
            WorkflowTelemetryEdge(source="docs", target="pr", label="documentation"),
        )

    def _telemetry_timeline(self, events: tuple[Any, ...]) -> tuple[WorkflowTelemetryTimelineItem, ...]:
        return tuple(
            WorkflowTelemetryTimelineItem(
                id=str(event.id),
                event_type=event.type.value,
                agent_name=event.agent_name,
                message=event.message,
                timestamp=event.timestamp,
                metadata=event.payload,
            )
            for event in events
        )

    def _telemetry_mermaid(self, nodes: tuple[WorkflowTelemetryNode, ...]) -> str:
        status_by_agent = {node.agent_name: node.status.value for node in nodes}
        return "\n".join(
            [
                "flowchart LR",
                f'  BA["BA ({status_by_agent["ba"]})"] --> Architect["Architect ({status_by_agent["architect"]})"]',
                f'  Architect --> Developer["Developer ({status_by_agent["developer"]})"]',
                f'  Developer --> QA["QA ({status_by_agent["qa"]})"]',
                f'  QA -->|approved| Docs["Docs ({status_by_agent["docs"]})"]',
                "  QA -->|rejected retry| Developer",
                f'  Docs --> PR["PR ({status_by_agent["pr"]})"]',
            ]
        )

    def _duration_ms(self, start: datetime, end: datetime) -> int:
        return max(0, int((end - start).total_seconds() * 1000))
