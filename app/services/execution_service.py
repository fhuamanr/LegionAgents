"""Execution application service."""

import asyncio
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from pathlib import Path
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
from core.agents.runtime import AgentModelClient
from core.ingestion import StoryIngestionPipeline
from core.streaming import (
    ExecutionEvent,
    ExecutionEventEmitter,
    ExecutionEventType,
    ExecutionLogLevel,
    ExecutionTracker,
    InMemoryExecutionEventBus,
    StructuredExecutionLogger,
    TimelineGenerator,
)
from core.graph import (
    InMemoryWorkflowExecutionRepository,
    LangGraphExecutionRuntime,
    WorkflowExecutionRepository,
    WorkflowRunStatus,
)
from core.persistence import PostgresJsonDocumentStore


class ExecutionService:
    """Application service for real workflow execution APIs."""

    def __init__(
        self,
        event_bus: InMemoryExecutionEventBus | None = None,
        model_client: AgentModelClient | None = None,
        workflow_repository: WorkflowExecutionRepository | None = None,
        state_store: PostgresJsonDocumentStore | None = None,
    ) -> None:
        self.event_bus = event_bus or InMemoryExecutionEventBus()
        self._model_client = model_client
        self.emitter = ExecutionEventEmitter(self.event_bus)
        self.logger = StructuredExecutionLogger(self.emitter)
        self.tracker = ExecutionTracker(self.event_bus)
        self.timeline = TimelineGenerator(self.event_bus)
        self.workflow_repository = workflow_repository or InMemoryWorkflowExecutionRepository()
        self._state_store = state_store
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
        self._ingestion = StoryIngestionPipeline()
        self._upload_root = Path("outputs/uploads").resolve()

    async def upload_user_story(self, request: UserStoryUploadRequest) -> UploadResponse:
        upload = StoredUpload(
            title=request.title,
            content=request.content,
            metadata=request.metadata,
        )
        self._uploads[upload.upload_id] = upload
        await self._persist_upload(upload)
        return UploadResponse(
            upload_id=upload.upload_id,
            title=upload.title,
            received_at=upload.received_at,
        )

    async def upload_file(
        self,
        *,
        file_name: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UploadResponse:
        upload_id = uuid4()
        safe_name = self._safe_upload_name(file_name)
        upload_path = self._upload_root / str(upload_id) / safe_name
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(content)
        ingestion = await self._ingestion.ingest_path(upload_path)
        upload = StoredUpload(
            upload_id=upload_id,
            title=file_name,
            content="\n\n".join(story.story.title for story in ingestion.stories) or ingestion.source.name,
            metadata={
                **(metadata or {}),
                "path": str(upload_path),
                "content_type": content_type,
                "ingestion": ingestion.model_dump(mode="json"),
            },
        )
        self._uploads[upload.upload_id] = upload
        await self._persist_upload(upload)
        return UploadResponse(
            upload_id=upload.upload_id,
            title=upload.title,
            received_at=upload.received_at,
        )

    async def trigger_workflow(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
        workflow = await self._initialize_workflow(request)
        return await self._execute_workflow(workflow.workflow_id, request)

    async def trigger_workflow_live(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
        """Start a workflow and return immediately for WebSocket subscribers."""

        workflow = await self._initialize_workflow(request)
        asyncio.create_task(self._execute_workflow(workflow.workflow_id, request))
        return workflow

    async def _initialize_workflow(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
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
        await self._persist_workflow(workflow)
        await self.tracker.start_workflow(workflow_id=workflow_id, total_steps=6)
        return workflow

    async def _execute_workflow(self, workflow_id: UUID, request: TriggerWorkflowRequest) -> WorkflowResponse:
        metadata: dict[str, Any] = dict(request.metadata)
        if request.upload_id:
            metadata["upload_id"] = str(request.upload_id)
        progress_hook = metadata.pop("progress_hook", None)
        runtime = LangGraphExecutionRuntime(
            repository=self.workflow_repository,
            model_client=self._model_client,
            event_hook=self._runtime_event_hook(
                workflow_id,
                request.thread_id,
                progress_hook if callable(progress_hook) else None,
            ),
            token_callback=self._token_callback(),
        )
        result = await runtime.start(
            request.task,
            workflow_id=workflow_id,
            metadata=metadata,
        )
        workflow = self._workflows[workflow_id]
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
        await self._persist_workflow(final_workflow)
        return final_workflow

    async def recover_workflow(
        self,
        workflow_id: UUID,
        metadata: dict[str, Any] | None = None,
        progress_hook: Callable[[ExecutionEvent], Awaitable[None]] | None = None,
    ) -> WorkflowResponse:
        """Recover a paused persisted workflow execution when a checkpoint exists."""

        workflow = self._workflows[workflow_id]
        execution_id = workflow.metadata.get("execution_id")
        if not execution_id:
            return await self.resume_workflow(workflow_id, metadata or {})
        runtime = LangGraphExecutionRuntime(
            repository=self.workflow_repository,
            model_client=self._model_client,
            event_hook=self._runtime_event_hook(workflow_id, workflow.thread_id, progress_hook),
            token_callback=self._token_callback(),
        )
        result = await runtime.recover(UUID(str(execution_id)))
        updated = workflow.model_copy(
            update={
                "status": self._workflow_status_from_run(result.status),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {
                    **workflow.metadata,
                    **(metadata or {}),
                    "runtime_status": result.status.value,
                    "checkpoint_count": len(result.checkpoints),
                },
            }
        )
        self._workflows[workflow_id] = updated
        await self._persist_workflow(updated)
        return updated

    async def get_workflow(self, workflow_id: UUID) -> WorkflowResponse:
        if workflow_id not in self._workflows:
            restored = await self._load_workflow(workflow_id)
            if restored is not None:
                self._workflows[workflow_id] = restored
        return self._workflows[workflow_id]

    async def latest_workflow(self) -> WorkflowResponse | None:
        if not self._workflows:
            await self._load_workflows()
        if not self._workflows:
            return None
        return max(self._workflows.values(), key=lambda workflow: workflow.created_at)

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
        await self._persist_workflow(updated)
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
        await self._persist_workflow(updated)
        return updated

    async def get_execution_status(self, workflow_id: UUID) -> ExecutionStatusResponse:
        workflow = await self.get_workflow(workflow_id)
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

        workflow = await self.get_workflow(workflow_id)
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
        workflow = await self.get_workflow(workflow_id)
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

    def _runtime_event_hook(
        self,
        workflow_id: UUID,
        thread_id: str | None,
        progress_hook: Callable[[ExecutionEvent], Awaitable[None]] | None = None,
    ):
        async def emit_runtime_event(event_name: str, state: dict[str, Any]) -> None:
            agent_name = str(state.get("next_agent") or state.get("last_agent") or "")
            event_type = self._runtime_event_type(event_name, agent_name)
            payload = self._runtime_event_payload(state, agent_name)
            event = await self.emitter.emit(
                event_type,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name or None,
                message=self._runtime_event_message(event_name, agent_name),
                payload=payload,
            )
            await self.tracker.apply_event(event)
            await self.logger.log(
                self._log_level_from_event(event_type),
                event.message,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                agent_name=agent_name or None,
                payload=payload,
            )
            if event_name == "agent_completed":
                await self._emit_generated_output(workflow_id, thread_id, state, agent_name)
            if progress_hook is not None:
                await progress_hook(event)
            if agent_name in self._agent_statuses:
                self._agent_statuses[agent_name] = self._agent_status_from_event(event_type)

        return emit_runtime_event

    def _token_callback(self):
        async def publish(
            workflow_id: UUID,
            execution_id: UUID,
            agent_name: str,
            token: str,
        ) -> None:
            await self.emitter.emit(
                ExecutionEventType.TOKEN_STREAMED,
                workflow_id=workflow_id,
                execution_id=execution_id,
                agent_name=agent_name,
                message=token,
                payload={
                    "token": token,
                    "character_count": len(token),
                    "estimated_tokens": max(1, len(token) // 4),
                },
            )

        return publish

    async def _emit_generated_output(
        self,
        workflow_id: UUID,
        thread_id: str | None,
        state: dict[str, Any],
        agent_name: str,
    ) -> None:
        workflow_state = state.get("workflow_state")
        snapshot = getattr(workflow_state, "agent_states", {}).get(agent_name) if workflow_state else None
        artifacts = tuple(
            artifact
            for artifact in getattr(workflow_state, "artifacts", tuple())
            if getattr(artifact, "producer_agent", None) == agent_name
        ) if workflow_state else tuple()
        payload: dict[str, Any] = {
            "summary": getattr(snapshot, "summary", ""),
            "status": getattr(getattr(snapshot, "status", None), "value", None),
            "artifact_count": len(artifacts),
            "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
            "metadata": getattr(snapshot, "metadata", {}) if snapshot else {},
        }
        await self.emitter.emit(
            ExecutionEventType.OUTPUT_GENERATED,
            workflow_id=workflow_id,
            execution_id=state.get("execution_id"),
            thread_id=thread_id,
            agent_name=agent_name,
            message=f"{self._agent_labels.get(agent_name, agent_name)} generated output.",
            payload=payload,
        )
        if agent_name == "qa":
            passed = bool(payload["metadata"].get("passed"))
            await self.emitter.emit(
                ExecutionEventType.TELEMETRY_RECORDED,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name,
                message="QA result recorded.",
                payload={
                    "qa": {
                        "passed": passed,
                        "summary": payload["summary"],
                        "artifact_count": len(artifacts),
                    }
                },
            )

    def _runtime_event_payload(self, state: dict[str, Any], agent_name: str) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in dict(state.get("metadata", {})).items()
            if not callable(value) and not str(key).startswith("_")
        }
        return {
            "attempts": state.get("attempts", {}),
            "status": state.get("status"),
            "active_agent": agent_name or None,
            "metadata": metadata,
        }

    def _log_level_from_event(self, event_type: ExecutionEventType) -> ExecutionLogLevel:
        if event_type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}:
            return ExecutionLogLevel.ERROR
        if event_type == ExecutionEventType.RETRY_STARTED:
            return ExecutionLogLevel.WARNING
        return ExecutionLogLevel.INFO

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

    async def _persist_workflow(self, workflow: WorkflowResponse) -> None:
        if self._state_store is None:
            return
        await self._state_store.upsert(
            bucket="api_workflows",
            document_id=workflow.workflow_id,
            key=workflow.created_at.isoformat(),
            payload=workflow.model_dump(mode="json"),
        )

    async def _load_workflow(self, workflow_id: UUID) -> WorkflowResponse | None:
        if self._state_store is None:
            return None
        try:
            payload = await self._state_store.get(bucket="api_workflows", document_id=workflow_id)
        except KeyError:
            return None
        return WorkflowResponse.model_validate(payload)

    async def _load_workflows(self) -> None:
        if self._state_store is None:
            return
        for payload in await self._state_store.list(bucket="api_workflows"):
            workflow = WorkflowResponse.model_validate(payload)
            self._workflows[workflow.workflow_id] = workflow

    async def _persist_upload(self, upload: StoredUpload) -> None:
        if self._state_store is None:
            return
        await self._state_store.upsert(
            bucket="uploads",
            document_id=upload.upload_id,
            key=upload.received_at.isoformat(),
            payload=upload.model_dump(mode="json"),
        )

    def _safe_upload_name(self, file_name: str) -> str:
        cleaned = "".join(character if character.isalnum() or character in ".-_" else "-" for character in file_name)
        return cleaned.strip(".-") or "upload.txt"
