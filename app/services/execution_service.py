"""Execution application service."""

import asyncio
import os
import json
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.schemas import (
    AgentPlaygroundArtifactListResponse,
    AgentPlaygroundArtifactSummary,
    AgentPlaygroundHandoffUpdateRequest,
    AgentPlaygroundRunRequest,
    AgentPlaygroundRunResponse,
    AgentPlaygroundWorkflowRunRequest,
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
    WorkflowArtifactListResponse,
    WorkflowArtifactFile,
    WorkflowResponse,
    WorkflowStatus,
)
from core.agents.runtime import AgentModelClient
from core.contracts.prompts import PromptMessage, PromptRole
from core.ingestion import StoryIngestionPipeline
from core.streaming import (
    ExecutionEventBus,
    ExecutionEvent,
    ExecutionEventEmitter,
    ExecutionEventType,
    ExecutionLogLevel,
    ExecutionTracker,
    InMemoryExecutionEventBus,
    StructuredExecutionLogger,
    TimelineGenerator,
)
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.execution import AgentExecutionRequest
from core.graph.runtime_agents import build_default_agent_runtimes
from core.runtime.context_governor import ContextGovernor
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
        event_bus: ExecutionEventBus | None = None,
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
        self._upload_root = Path(os.getenv("UPLOAD_ROOT", "outputs/uploads")).resolve()
        self._artifact_root = Path(os.getenv("ARTIFACT_ROOT", "data/artifacts")).resolve()
        self._local_safe_mode_semaphore = asyncio.Semaphore(1)
        self._playground_artifacts: dict[UUID, list[AgentPlaygroundArtifactSummary]] = {}
        self._context_governor = ContextGovernor()

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
        request = await self._hydrate_upload_context(request)
        workflow = await self._initialize_workflow(request)
        return await self._execute_workflow(workflow.workflow_id, request)

    async def trigger_workflow_with_toggles(self, request: AgentPlaygroundWorkflowRunRequest) -> WorkflowResponse:
        metadata = dict(request.metadata)
        metadata["enabled_agents"] = list(request.enabled_agents)
        metadata["execution_mode"] = request.execution_mode
        trigger = TriggerWorkflowRequest(task=request.task, metadata=metadata)
        return await self.trigger_workflow(trigger)

    async def trigger_workflow_live(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
        """Start a workflow and return immediately for WebSocket subscribers."""
        request = await self._hydrate_upload_context(request)
        workflow = await self._initialize_workflow(request)
        asyncio.create_task(self._execute_workflow(workflow.workflow_id, request))
        return workflow

    async def _initialize_workflow(self, request: TriggerWorkflowRequest) -> WorkflowResponse:
        now = datetime.now(timezone.utc)
        workflow_id = uuid4()
        metadata: dict[str, Any] = {
            key: value
            for key, value in dict(request.metadata).items()
            if not callable(value) and not str(key).startswith("_")
        }
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
        created_event = ExecutionEvent(
            type=ExecutionEventType.PROGRESS_UPDATED,
            workflow_id=workflow_id,
            thread_id=request.thread_id,
            message="Workflow created and queued for execution.",
            payload={"status": workflow.status.value, "task": workflow.task},
        )
        await self.event_bus.publish(created_event)
        await self.logger.log(
            ExecutionLogLevel.INFO,
            "Workflow created and started.",
            workflow_id=workflow_id,
            payload={"status": workflow.status.value},
        )
        return workflow

    async def _execute_workflow(self, workflow_id: UUID, request: TriggerWorkflowRequest) -> WorkflowResponse:
        metadata: dict[str, Any] = dict(request.metadata)
        local_safe_mode = str(os.getenv("LOCAL_LM_STUDIO_SAFE_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}
        metadata.setdefault("local_lm_studio_safe_mode", local_safe_mode)
        if local_safe_mode and "workflow_mode" not in metadata and "workflow_type" not in metadata:
            metadata["workflow_mode"] = "ba_only"
        if request.upload_id:
            metadata["upload_id"] = str(request.upload_id)
        progress_hook = metadata.pop("progress_hook", None)
        runtime = LangGraphExecutionRuntime(
            repository=self.workflow_repository,
            model_client=self._model_client,
            execution_owner="backend",
            event_hook=self._runtime_event_hook(
                workflow_id,
                request.thread_id,
                progress_hook if callable(progress_hook) else None,
            ),
            token_callback=self._token_callback(),
        )
        if local_safe_mode:
            async with self._local_safe_mode_semaphore:
                result = await runtime.start(
                    request.task,
                    workflow_id=workflow_id,
                    metadata=metadata,
                )
        else:
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
                    "artifacts_root": str(self._artifact_root / str(workflow_id)),
                },
            }
        )
        self._workflows[workflow_id] = final_workflow
        await self._persist_workflow(final_workflow)
        await self.event_bus.publish(
            ExecutionEvent(
                type=ExecutionEventType.PROGRESS_UPDATED,
                workflow_id=workflow_id,
                thread_id=request.thread_id,
                message=f"Workflow finished with status {final_workflow.status.value}.",
                payload={
                    "status": final_workflow.status.value,
                    "execution_id": str(result.execution_id),
                    "checkpoint_count": len(result.checkpoints),
                },
            )
        )
        return final_workflow

    async def run_agent_playground(self, request: AgentPlaygroundRunRequest) -> AgentPlaygroundRunResponse:
        workflow_id = request.workflow_id or uuid4()
        execution_id = uuid4()
        source_text, warnings = await self._resolve_playground_input(request, workflow_id)
        if request.local_lm_studio_safe_mode:
            budget = self._context_governor.budget_for(request.agent_name, local_compact_mode=True)
            estimated = self._context_governor.estimate_tokens(source_text)
            if estimated > budget.prompt_max_tokens:
                raise ValueError(
                    f"Prompt exceeds local budget for {request.agent_name}. estimated={estimated} budget={budget.prompt_max_tokens}. "
                    "Trim input or use compact mode."
                )
        metadata = {
            **request.metadata,
            "provider_id": request.provider_id,
            "model": request.model,
            "local_lm_studio_safe_mode": request.local_lm_studio_safe_mode,
            "compact_mode_enabled": request.compact_mode_enabled,
            "workflow_mode": "ba_only" if request.agent_name == "ba" else "manual_step",
            "execution_mode": "manual_step",
        }
        step_request = AgentExecutionRequest(
            execution_id=execution_id,
            workflow_id=workflow_id,
            agent_name=request.agent_name,
            task=source_text,
            upstream_artifacts=tuple(self._artifacts_as_upstream(workflow_id, request.previous_agent)),
            metadata=metadata,
        )
        runtimes = build_default_agent_runtimes(model_client=self._model_client)
        runtime = runtimes[request.agent_name]
        result = await runtime.execute(step_request)
        raw_output = self._extract_raw_output(result)
        structured = result.metadata.get("structured_output", {}) if isinstance(result.metadata, dict) else {}
        handoff = self._derive_handoff(result, structured)
        token_report = {
            "input_tokens": int(result.metadata.get("observability", {}).get("prompt_token_estimate", 0)) if isinstance(result.metadata, dict) else 0,
            "output_tokens": int(result.metadata.get("observability", {}).get("output_token_estimate", 0)) if isinstance(result.metadata, dict) else 0,
            "handoff_tokens": max(1, len(handoff) // 4),
            "duration_seconds": result.metadata.get("observability", {}).get("generation_duration_seconds") if isinstance(result.metadata, dict) else None,
            "provider_id": request.provider_id,
            "model_id": request.model,
            "validation": result.metadata.get("validation", {}) if isinstance(result.metadata, dict) else {},
        }
        artifact = AgentPlaygroundArtifactSummary(
            id=f"{workflow_id}:{execution_id}:{request.agent_name}",
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=request.agent_name,
            provider_id=request.provider_id,
            model_id=request.model,
            raw_output=raw_output,
            structured_output=structured if isinstance(structured, dict) else {},
            handoff=handoff,
            execution_log="\n".join(result.errors) if result.errors else f"{request.agent_name} completed",
            token_report=token_report,
            created_at=datetime.now(timezone.utc),
        )
        self._playground_artifacts.setdefault(workflow_id, []).append(artifact)
        await self._persist_playground_artifact(artifact)
        return AgentPlaygroundRunResponse(artifact=artifact, warnings=tuple(warnings))

    async def list_agent_playground_artifacts(self, workflow_id: UUID) -> AgentPlaygroundArtifactListResponse:
        artifacts = list(self._playground_artifacts.get(workflow_id, []))
        if not artifacts and self._state_store is not None:
            loaded = await self._load_playground_artifacts(workflow_id)
            self._playground_artifacts[workflow_id] = loaded
            artifacts = list(loaded)
        return AgentPlaygroundArtifactListResponse(artifacts=tuple(artifacts))

    async def update_playground_handoff(self, workflow_id: UUID, execution_id: UUID, request: AgentPlaygroundHandoffUpdateRequest) -> AgentPlaygroundArtifactSummary:
        artifacts = self._playground_artifacts.get(workflow_id, [])
        for index, artifact in enumerate(artifacts):
            if artifact.execution_id == execution_id:
                updated = artifact.model_copy(update={"handoff": request.handoff})
                artifacts[index] = updated
                await self._persist_playground_artifact(updated)
                return updated
        raise KeyError(str(execution_id))

    def _artifacts_as_upstream(self, workflow_id: UUID, previous_agent: str | None) -> tuple[Artifact, ...]:
        artifacts = self._playground_artifacts.get(workflow_id, [])
        selected = [item for item in artifacts if previous_agent is None or item.agent_name == previous_agent]
        if not selected:
            return tuple()
        latest = selected[-1]
        return (
            Artifact(
                id=f"playground-handoff-{latest.execution_id}",
                kind=ArtifactKind.GENERIC,
                name=f"{latest.agent_name} handoff",
                producer_agent=latest.agent_name,
                content=latest.handoff,
                metadata={"source": "playground_handoff"},
            ),
        )

    async def _resolve_playground_input(self, request: AgentPlaygroundRunRequest, workflow_id: UUID) -> tuple[str, list[str]]:
        warnings: list[str] = []
        if request.input_source == "manual_prompt":
            return request.prompt.strip(), warnings
        if request.input_source == "uploaded_file":
            return (request.uploaded_text or "").strip(), warnings
        artifacts = self._playground_artifacts.get(workflow_id, [])
        if request.input_source == "previous_agent_raw_output":
            candidates = [item for item in artifacts if request.previous_agent is None or item.agent_name == request.previous_agent]
            if candidates:
                return candidates[-1].raw_output, warnings
            warnings.append("No previous raw output found; using manual prompt.")
            return request.prompt.strip(), warnings
        if request.input_source == "previous_agent_handoff":
            candidates = [item for item in artifacts if request.previous_agent is None or item.agent_name == request.previous_agent]
            if candidates:
                return candidates[-1].handoff, warnings
            warnings.append("No previous handoff found; using manual prompt.")
            return request.prompt.strip(), warnings
        if request.input_source == "saved_artifact" and request.artifact_id:
            for item in artifacts:
                if item.id == request.artifact_id:
                    return item.handoff or item.raw_output, warnings
            warnings.append("Saved artifact not found; using manual prompt.")
        return request.prompt.strip(), warnings

    def _extract_raw_output(self, result) -> str:
        if not result.artifacts:
            return result.summary
        return str(result.artifacts[0].content or result.summary)

    def _derive_handoff(self, result, structured: dict[str, Any]) -> str:
        handoff = ""
        if isinstance(result.metadata, dict):
            handoff = str(result.metadata.get("handoff_summary", "")).strip()
        if handoff:
            return handoff
        if structured:
            summary = str(structured.get("summary", "")).strip()
            if summary:
                return summary[:1200]
        return result.summary[:1200]

    async def _persist_playground_artifact(self, artifact: AgentPlaygroundArtifactSummary) -> None:
        if self._state_store is None:
            return
        await self._state_store.upsert(
            bucket="agent_playground_artifacts",
            document_id=artifact.execution_id,
            key=f"{artifact.workflow_id}:{artifact.agent_name}:{artifact.created_at.isoformat()}",
            payload=artifact.model_dump(mode="json"),
        )

    async def _load_playground_artifacts(self, workflow_id: UUID) -> list[AgentPlaygroundArtifactSummary]:
        if self._state_store is None:
            return []
        loaded: list[AgentPlaygroundArtifactSummary] = []
        for payload in await self._state_store.list(bucket="agent_playground_artifacts", key_prefix=f"{workflow_id}:"):
            loaded.append(AgentPlaygroundArtifactSummary.model_validate(payload))
        return loaded

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
            execution_owner="backend",
            event_hook=self._runtime_event_hook(workflow_id, workflow.thread_id, progress_hook),
            token_callback=self._token_callback(),
        )
        local_safe_mode = bool(workflow.metadata.get("local_lm_studio_safe_mode", False))
        if local_safe_mode:
            async with self._local_safe_mode_semaphore:
                result = await runtime.recover(UUID(str(execution_id)))
        else:
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
        events = await self.event_bus.history(workflow_id=workflow_id)
        return ExecutionStatusResponse(
            workflow_id=workflow_id,
            status=workflow.status,
            active_agent=progress.active_agent if progress else None,
            progress_percent=self._compute_progress_percent(workflow, events, progress.active_agent if progress else None),
            metadata=workflow.metadata,
        )

    async def get_logs(self, workflow_id: UUID) -> ExecutionLogResponse:
        events = await self.event_bus.history(workflow_id=workflow_id)
        return ExecutionLogResponse(
            workflow_id=workflow_id,
            events=tuple(event.model_dump(mode="json") for event in events),
        )

    async def list_workflow_artifacts(self, workflow_id: UUID, agent_name: str | None = None) -> WorkflowArtifactListResponse:
        root = self._artifact_root / str(workflow_id)
        files: list[WorkflowArtifactFile] = []
        if not root.exists():
            return WorkflowArtifactListResponse(workflow_id=workflow_id, files=tuple())
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            parts = rel.split("/", 1)
            if not parts:
                continue
            producer = parts[0]
            if agent_name and producer != agent_name:
                continue
            preview = ""
            try:
                preview = path.read_text(encoding="utf-8", errors="ignore")[:2000]
            except Exception:
                preview = ""
            stat = path.stat()
            files.append(
                WorkflowArtifactFile(
                    name=path.name,
                    agent_name=producer,
                    relative_path=rel,
                    absolute_path=str(path),
                    size_bytes=int(stat.st_size),
                    created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    preview=preview,
                )
            )
        files.sort(key=lambda item: (item.agent_name, item.relative_path))
        return WorkflowArtifactListResponse(workflow_id=workflow_id, files=tuple(files))

    async def read_workflow_artifact(self, workflow_id: UUID, agent_name: str, artifact_name: str) -> WorkflowArtifactFile:
        root = (self._artifact_root / str(workflow_id) / agent_name).resolve()
        path = (root / artifact_name).resolve()
        if root not in path.parents and path != root:
            raise KeyError(str(path))
        if not path.exists() or not path.is_file():
            raise KeyError(str(path))
        stat = path.stat()
        preview = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        return WorkflowArtifactFile(
            name=path.name,
            agent_name=agent_name,
            relative_path=f"{agent_name}/{artifact_name}".replace("\\", "/"),
            absolute_path=str(path),
            size_bytes=int(stat.st_size),
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            preview=preview,
        )

    async def get_workflow_telemetry(self, workflow_id: UUID) -> WorkflowTelemetryResponse:
        """Build a live visualization snapshot for a workflow."""

        workflow = await self.get_workflow(workflow_id)
        events = await self.event_bus.history(workflow_id=workflow_id)
        progress = await self.tracker.get(workflow_id)
        now = datetime.now(timezone.utc)
        nodes = self._telemetry_nodes(events, now)
        progress_percent = self._compute_progress_percent(workflow, events, progress.active_agent if progress else None)
        return WorkflowTelemetryResponse(
            workflow_id=workflow_id,
            status=workflow.status,
            active_agent=progress.active_agent if progress else None,
            progress_percent=progress_percent,
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
                "stage_label": self._stage_label(progress.active_agent if progress else None, workflow.status),
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

    async def complete_chat(self, content: str) -> str:
        if self._model_client is None:
            raise ValueError("No provider is configured.")
        return await self._model_client.complete(
            (
                PromptMessage(role=PromptRole.SYSTEM, content="You are the AI Workspace assistant for Legion Agents."),
                PromptMessage(role=PromptRole.USER, content=content),
            )
        )

    async def stream_chat(self, content: str):
        if self._model_client is None:
            raise ValueError("No provider is configured.")
        messages = (
            PromptMessage(role=PromptRole.SYSTEM, content="You are the AI Workspace assistant for Legion Agents."),
            PromptMessage(role=PromptRole.USER, content=content),
        )
        if hasattr(self._model_client, "stream_complete"):
            async for chunk in self._model_client.stream_complete(messages):  # type: ignore[attr-defined]
                if chunk:
                    yield chunk
            return
        result = await self._model_client.complete(messages)
        if result:
            yield result

    def _runtime_event_hook(
        self,
        workflow_id: UUID,
        thread_id: str | None,
        progress_hook: Callable[[ExecutionEvent], Awaitable[None]] | None = None,
    ):
        async def emit_runtime_event(event_name: str, state: dict[str, Any]) -> None:
            agent_name = str(state.get("next_agent") or state.get("last_agent") or "")
            if event_name in {
                "context_budget_estimated",
                "context_compressed",
                "handoff_generated",
                "oversized_prompt_blocked",
                "compact_mode_enabled",
                "stage_transition",
                "provider_selected_per_agent",
            }:
                payload = self._runtime_event_payload(state, agent_name)
                payload["event"] = event_name
                event = await self.emitter.emit(
                    ExecutionEventType.TELEMETRY_RECORDED,
                    workflow_id=workflow_id,
                    execution_id=state.get("execution_id"),
                    thread_id=thread_id,
                    agent_name=agent_name or None,
                    message=event_name,
                    payload=payload,
                )
                await self.logger.log(
                    ExecutionLogLevel.INFO,
                    event_name,
                    workflow_id=workflow_id,
                    execution_id=state.get("execution_id"),
                    agent_name=agent_name or None,
                    payload=payload,
                )
                if progress_hook is not None:
                    await progress_hook(event)
                return
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
            if event_name in {"agent_completed", "agent_failed"}:
                await self._persist_agent_artifact_bundle(workflow_id, state, agent_name, event_name)
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
        validation_meta = payload["metadata"].get("validation", {}) if isinstance(payload["metadata"], dict) else {}
        if validation_meta.get("sanitization_applied"):
            await self.emitter.emit(
                ExecutionEventType.TELEMETRY_RECORDED,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name,
                message="output_sanitized",
                payload={
                    "event": "output_sanitized",
                    "agent": agent_name,
                    "schema_name": validation_meta.get("schema_name"),
                    "fields_removed": validation_meta.get("fields_removed", []),
                },
            )
        if validation_meta.get("json_repaired"):
            await self.emitter.emit(
                ExecutionEventType.TELEMETRY_RECORDED,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name,
                message="output_repaired",
                payload={
                    "event": "output_repaired",
                    "agent_name": agent_name,
                    "repair_strategy": validation_meta.get("repair_strategy"),
                    "repair_actions": validation_meta.get("repair_actions", []),
                },
            )
        if validation_meta.get("artifact_fallback_used"):
            await self.emitter.emit(
                ExecutionEventType.TELEMETRY_RECORDED,
                workflow_id=workflow_id,
                execution_id=state.get("execution_id"),
                thread_id=thread_id,
                agent_name=agent_name,
                message="artifact_fallback_used",
                payload={
                    "event": "artifact_fallback_used",
                    "agent_name": agent_name,
                    "extraction_strategy": validation_meta.get("extraction_strategy"),
                },
            )

    async def _persist_agent_artifact_bundle(
        self,
        workflow_id: UUID,
        state: dict[str, Any],
        agent_name: str,
        event_name: str,
    ) -> None:
        workflow_state = state.get("workflow_state")
        snapshot = getattr(workflow_state, "agent_states", {}).get(agent_name) if workflow_state else None
        if snapshot is None:
            return
        metadata = getattr(snapshot, "metadata", {}) or {}
        summary = getattr(snapshot, "summary", "") or ""
        agent_root = self._artifact_root / str(workflow_id) / agent_name
        agent_root.mkdir(parents=True, exist_ok=True)

        prompt_messages = metadata.get("prompt_messages", [])
        if isinstance(prompt_messages, list) and prompt_messages:
            system_chunks = [str(item.get("content", "")) for item in prompt_messages if isinstance(item, dict) and str(item.get("role", "")).lower() == "system"]
            user_chunks = [str(item.get("content", "")) for item in prompt_messages if isinstance(item, dict) and str(item.get("role", "")).lower() == "user"]
            (agent_root / "prompt.md").write_text("\n\n".join(str(item.get("content", "")) for item in prompt_messages if isinstance(item, dict)), encoding="utf-8")
            (agent_root / "system_prompt.md").write_text("\n\n".join(system_chunks), encoding="utf-8")
            (agent_root / "user_prompt.md").write_text("\n\n".join(user_chunks), encoding="utf-8")
            (agent_root / "context_used.md").write_text("\n\n".join(user_chunks)[:12000], encoding="utf-8")

        raw_output = str(metadata.get("raw_output", "")).strip()
        if raw_output:
            (agent_root / "raw_output.md").write_text(raw_output, encoding="utf-8")
        elif summary:
            (agent_root / "raw_output.md").write_text(summary, encoding="utf-8")

        structured = metadata.get("structured_output", {})
        if isinstance(structured, dict) and structured:
            (agent_root / "structured_output.json").write_text(json.dumps(structured, indent=2, ensure_ascii=False), encoding="utf-8")
            handoff = str(metadata.get("handoff_summary") or structured.get("summary") or summary).strip()
            if handoff:
                (agent_root / "handoff.md").write_text(handoff, encoding="utf-8")
        if event_name == "agent_failed":
            errors = list(getattr(snapshot, "errors", tuple()) or [])
            if errors:
                (agent_root / "validation_error.txt").write_text("\n".join(str(item) for item in errors), encoding="utf-8")

        validation = metadata.get("validation", {})
        observability = metadata.get("observability", {})
        if isinstance(validation, dict):
            repaired_output = validation.get("repaired_output")
            normalized_output = validation.get("normalized_output")
            repair_report = validation.get("repair_report")
            if isinstance(repaired_output, str) and repaired_output.strip():
                (agent_root / "repaired_output.json").write_text(repaired_output, encoding="utf-8")
            if isinstance(normalized_output, dict) and normalized_output:
                (agent_root / "normalized_output.json").write_text(
                    json.dumps(normalized_output, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            if isinstance(repair_report, dict) and repair_report:
                (agent_root / "repair_report.json").write_text(
                    json.dumps(repair_report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        token_report = {
            "prompt_tokens": observability.get("prompt_token_estimate"),
            "output_tokens": observability.get("output_token_estimate"),
            "duration_seconds": observability.get("generation_duration_seconds"),
            "validation": validation,
        }
        (agent_root / "token_report.json").write_text(json.dumps(token_report, indent=2, ensure_ascii=False), encoding="utf-8")
        (agent_root / "execution_log.txt").write_text(
            f"agent={agent_name}\nstatus={getattr(getattr(snapshot, 'status', None), 'value', None)}\nsummary={summary}\n",
            encoding="utf-8",
        )
        if agent_name == "developer" and isinstance(structured, dict):
            await self._persist_developer_files(agent_root, structured)
        if agent_name == "docs":
            markdown = ""
            if isinstance(structured, dict):
                markdown = str((structured.get("metadata", {}) or {}).get("documentation_markdown", "")).strip() if isinstance(structured.get("metadata", {}), dict) else ""
            if not markdown:
                markdown = raw_output or summary
            if markdown:
                (agent_root / "documentation.md").write_text(markdown, encoding="utf-8")
            if "```mermaid" in markdown:
                diagrams_dir = agent_root / "diagrams"
                diagrams_dir.mkdir(parents=True, exist_ok=True)
                blocks = markdown.split("```mermaid")
                index = 0
                for block in blocks[1:]:
                    body = block.split("```", 1)[0].strip()
                    if body:
                        (diagrams_dir / f"diagram-{index}.mmd").write_text(body, encoding="utf-8")
                        index += 1

    async def _persist_developer_files(self, agent_root: Path, structured: dict[str, Any]) -> None:
        code_dir = agent_root / "code"
        test_dir = agent_root / "tests"
        code_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        patch_lines: list[str] = []
        for change in structured.get("code_changes", []) if isinstance(structured.get("code_changes", []), list) else []:
            if not isinstance(change, dict):
                continue
            path = str(change.get("path", "")).strip() or "generated/unknown.tsx"
            content = str(change.get("content", "") or "")
            target = code_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            patch_lines.append(f"--- /dev/null\n+++ b/{path}\n{content}\n")
        for test in structured.get("tests", []) if isinstance(structured.get("tests", []), list) else []:
            if not isinstance(test, dict):
                continue
            path = str(test.get("path", "")).strip() or "generated/unknown.test.tsx"
            content = str(test.get("content", "") or "")
            target = test_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            patch_lines.append(f"--- /dev/null\n+++ b/{path}\n{content}\n")
        if patch_lines:
            (agent_root / "patch.diff").write_text("\n".join(patch_lines), encoding="utf-8")

    def _runtime_event_payload(self, state: dict[str, Any], agent_name: str) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in dict(state.get("metadata", {})).items()
            if not callable(value) and not str(key).startswith("_")
        }
        attempts = dict(state.get("attempts", {}))
        snapshot = None
        workflow_state = state.get("workflow_state")
        if workflow_state and agent_name:
            snapshot = getattr(workflow_state, "agent_states", {}).get(agent_name)
        return {
            "attempts": attempts,
            "status": state.get("status"),
            "active_agent": agent_name or None,
            "workflow_id": str(state["workflow_state"].workflow_id) if state.get("workflow_state") else None,
            "agent": agent_name or None,
            "attempt": attempts.get(agent_name, 0) if agent_name else 0,
            "execution_owner": metadata.get("execution_owner"),
            "provider_call_id": metadata.get("provider_call_id"),
            "agent_error_type": getattr(snapshot, "metadata", {}).get("error_type") if snapshot else None,
            "agent_errors": list(getattr(snapshot, "errors", tuple())) if snapshot else [],
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

    def _compute_progress_percent(
        self,
        workflow: WorkflowResponse,
        events: tuple[Any, ...],
        active_agent: str | None,
    ) -> float:
        ba_only = str(workflow.metadata.get("workflow_mode", workflow.metadata.get("workflow_type", ""))).lower() in {"ba_only", "ba-only"}
        if ba_only:
            if workflow.status in {WorkflowStatus.COMPLETED}:
                return 100.0
            if active_agent == "ba":
                return 50.0
            return 0.0
        completed_agents = {
            event.agent_name
            for event in events
            if event.type in {ExecutionEventType.AGENT_COMPLETED, ExecutionEventType.DOCS_GENERATED, ExecutionEventType.PR_GENERATED}
        }
        if workflow.status == WorkflowStatus.COMPLETED:
            return 100.0
        if "pr" in completed_agents:
            return 100.0
        if "docs" in completed_agents:
            return 90.0
        if "qa" in completed_agents:
            return 75.0
        if "developer" in completed_agents:
            return 60.0
        if "architect" in completed_agents:
            return 40.0
        if "ba" in completed_agents:
            return 20.0
        if active_agent == "ba":
            return 10.0
        return 0.0

    def _stage_label(self, active_agent: str | None, status: WorkflowStatus) -> str:
        if status == WorkflowStatus.FAILED:
            return "Failed"
        if status == WorkflowStatus.COMPLETED:
            return "Completed"
        if active_agent:
            return f"{active_agent} running"
        return "Created"

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

    async def _hydrate_upload_context(self, request: TriggerWorkflowRequest) -> TriggerWorkflowRequest:
        if request.upload_id is None:
            return request
        upload = self._uploads.get(request.upload_id)
        if upload is None and self._state_store is not None:
            try:
                payload = await self._state_store.get(bucket="uploads", document_id=request.upload_id)
                upload = StoredUpload.model_validate(payload)
                self._uploads[upload.upload_id] = upload
            except KeyError:
                upload = None
        if upload is None:
            return request
        enriched_task = f"{request.task}\n\nUploaded context ({upload.title}):\n{upload.content[:4000]}"
        return request.model_copy(
            update={
                "task": enriched_task,
                "metadata": {**request.metadata, "upload_title": upload.title},
            }
        )
