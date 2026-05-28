"""Execution application service."""

import asyncio
import os
import json
import re
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.schemas import (
    ImproveExecutionRequest,
    ImproveExecutionResponse,
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
        metadata.setdefault(
            "quality_rules",
            {
                "placeholder_density_warning_threshold": 0.03,
                "require_validations": True,
                "require_tests": True,
                "require_api_contracts": True,
                "require_documentation": True,
            },
        )
        metadata.setdefault("developer_passes", 6 if not local_safe_mode else 2)
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

    async def improve_existing_execution(self, workflow_id: UUID, request: ImproveExecutionRequest) -> ImproveExecutionResponse:
        source_root = Path(request.artifact_root).resolve()
        if not source_root.exists():
            raise KeyError(str(source_root))

        improvements_root = (self._artifact_root / str(workflow_id) / "improvements").resolve()
        improvements_root.mkdir(parents=True, exist_ok=True)

        summary = self._collect_artifact_quality_summary(source_root, request.selected_agents)
        quality_report = self._build_quality_report_markdown(summary, source_root)
        quality_report_path = improvements_root / "quality_report.md"
        quality_report_path.write_text(quality_report, encoding="utf-8")

        if "ba" in request.selected_agents:
            self._write_ba_improvement_docs(source_root, improvements_root)
        if "architect" in request.selected_agents:
            self._write_architect_improvement_docs(source_root, improvements_root)
        if "developer" in request.selected_agents:
            self._write_developer_improvement_docs(source_root, improvements_root)
        if "qa" in request.selected_agents:
            self._write_qa_improvement_docs(source_root, improvements_root)
        if "docs" in request.selected_agents:
            self._write_docs_improvement_docs(source_root, improvements_root)

        return ImproveExecutionResponse(
            workflow_id=workflow_id,
            improvements_path=str(improvements_root),
            quality_report_path=str(quality_report_path),
            quality_metrics=summary["metrics"],
            weaknesses=tuple(summary["weaknesses"]),
            strengths=tuple(summary["strengths"]),
        )

    def _collect_artifact_quality_summary(self, source_root: Path, selected_agents: tuple[str, ...]) -> dict[str, Any]:
        weaknesses: list[str] = []
        strengths: list[str] = []
        metrics: dict[str, float] = {}

        for agent in selected_agents:
            structured_path = source_root / agent / "structured_output.json"
            raw_path = source_root / agent / "raw_output.md"
            if not structured_path.exists() and not raw_path.exists():
                weaknesses.append(f"{agent}: missing structured/raw output artifacts.")
                metrics[f"{agent}_completeness"] = 0.0
                continue

            content = ""
            structured: dict[str, Any] = {}
            if structured_path.exists():
                content = structured_path.read_text(encoding="utf-8", errors="ignore")
                try:
                    structured = json.loads(content)
                except json.JSONDecodeError:
                    weaknesses.append(f"{agent}: structured_output.json is not valid JSON.")
            elif raw_path.exists():
                content = raw_path.read_text(encoding="utf-8", errors="ignore")

            tokenish = max(1, len(content) // 4)
            placeholder_hits = len(re.findall(r"\b(TODO|placeholder|insert|lorem|draft)\b", content, flags=re.IGNORECASE))
            placeholder_density = placeholder_hits / max(1, tokenish)
            completeness = max(0.0, min(1.0, (tokenish / 450.0) * (1.0 - min(0.8, placeholder_density))))
            metrics[f"{agent}_completeness"] = round(completeness * 100, 2)
            metrics[f"{agent}_placeholder_density"] = round(placeholder_density, 4)

            if completeness < 0.45:
                weaknesses.append(f"{agent}: output depth is shallow (score={metrics[f'{agent}_completeness']}).")
            else:
                strengths.append(f"{agent}: produced non-trivial output volume.")
            if placeholder_density > 0.03:
                weaknesses.append(f"{agent}: placeholder-heavy content detected (density={metrics[f'{agent}_placeholder_density']}).")

            if agent == "developer" and structured:
                code_changes = structured.get("code_changes", [])
                tests = structured.get("tests", [])
                if len(code_changes) < 3:
                    weaknesses.append("developer: insufficient code_changes breadth for realistic starter implementation.")
                if len(tests) < 3:
                    weaknesses.append("developer: insufficient test depth.")
                if code_changes:
                    strengths.append("developer: emitted concrete file-level code changes.")
            if agent == "qa" and structured:
                if not structured.get("test_reports"):
                    weaknesses.append("qa: missing test_reports and execution evidence.")
                if not structured.get("findings"):
                    weaknesses.append("qa: no findings matrix produced; quality assessment is superficial.")
            if agent == "docs" and structured:
                docs = structured.get("documents", [])
                if not docs:
                    weaknesses.append("docs: no structured documentation package entries were generated.")

        completeness_values = [value for key, value in metrics.items() if key.endswith("_completeness")]
        implementation_depth = sum(completeness_values) / max(1, len(completeness_values))
        metrics["implementation_depth"] = round(implementation_depth, 2)
        metrics["runnable_project_readiness"] = round(max(0.0, implementation_depth - 15.0), 2)
        return {
            "strengths": strengths[:12],
            "weaknesses": weaknesses[:24],
            "metrics": metrics,
        }

    def _build_quality_report_markdown(self, summary: dict[str, Any], source_root: Path) -> str:
        metrics = summary["metrics"]
        strengths = summary["strengths"]
        weaknesses = summary["weaknesses"]
        lines = [
            "# Delivery Quality Report",
            "",
            f"Source artifacts: `{source_root}`",
            "",
            "## Strengths",
        ]
        lines.extend(f"- {item}" for item in (strengths or ["No major strengths detected."]))
        lines.extend(["", "## Weaknesses"])
        lines.extend(f"- {item}" for item in (weaknesses or ["No major weaknesses detected."]))
        lines.extend(
            [
                "",
                "## Delivery Metrics",
                "",
                f"- Implementation depth score: **{metrics.get('implementation_depth', 0):.2f}/100**",
                f"- Runnable project readiness: **{metrics.get('runnable_project_readiness', 0):.2f}/100**",
                "",
                "## Agent Completeness",
            ]
        )
        for key, value in metrics.items():
            if key.endswith("_completeness"):
                lines.append(f"- {key}: {value:.2f}")
        lines.extend(
            [
                "",
                "## Missing Deliverables",
                "- Rich backend API contracts and service/repository logic.",
                "- Deeper QA evidence (test plan, coverage and edge-case matrix).",
                "- Production-grade documentation pack with setup/deployment/troubleshooting.",
                "- Architecture package with diagrams, DB design, observability and deployment plan.",
                "",
                "## Recommendations",
                "- Enable multi-pass developer generation to separate scaffolding, implementation, hardening and tests.",
                "- Increase agent-specific output contracts toward file bundles instead of summary-only JSON.",
                "- Apply quality-rule warnings for placeholder density, missing validations, and missing test evidence.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _read_structured_json(self, source_root: Path, agent: str) -> dict[str, Any]:
        path = source_root / agent / "structured_output.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return {}

    def _write_ba_improvement_docs(self, source_root: Path, improvements_root: Path) -> None:
        ba = self._read_structured_json(source_root, "ba")
        target = improvements_root / "ba"
        target.mkdir(parents=True, exist_ok=True)
        stories = ba.get("user_stories", []) if isinstance(ba, dict) else []
        requirement = str(ba.get("normalized_requirement", "")).strip() if isinstance(ba, dict) else ""
        functional_spec = [
            "# Functional Specification",
            "",
            "## Executive Summary",
            requirement or "MVP e-commerce platform with products, users, and shopping cart.",
            "",
            "## Scope",
            "- Product catalog browsing",
            "- User registration/authentication",
            "- Shopping cart management",
            "",
            "## Functional Requirements",
            "- FR-1: List products with pagination/search filters.",
            "- FR-2: Register/login users and persist session.",
            "- FR-3: Add/update/remove cart items and compute totals.",
            "",
            "## Non-Functional Requirements",
            "- API response time under 500ms in local dev for core endpoints.",
            "- Input validation and explicit error contracts for all write operations.",
            "- Observability logs for critical user and cart flows.",
            "",
            "## User Stories",
        ]
        if stories:
            for index, story in enumerate(stories[:5], start=1):
                functional_spec.append(f"- US-{index}: {story.get('narrative') or story.get('title')}")
        else:
            functional_spec.extend(
                [
                    "- As a buyer, I want to browse products and see prices/stock.",
                    "- As a buyer, I want to manage my cart before checkout.",
                    "- As a user, I want account-based cart persistence.",
                ]
            )
        (target / "functional_specification.md").write_text("\n".join(functional_spec) + "\n", encoding="utf-8")
        (target / "business_rules.md").write_text(
            "\n".join(
                [
                    "# Business Rules",
                    "",
                    "- BR-1: Cart quantity cannot exceed available inventory.",
                    "- BR-2: Product price used in cart is snapshotted at add-to-cart time.",
                    "- BR-3: Only authenticated users can persist carts.",
                    "- BR-4: Soft-delete products should not be purchasable.",
                    "- BR-5: Currency and tax calculations are deterministic and auditable.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "requirements_matrix.md").write_text(
            "\n".join(
                [
                    "# Requirements Matrix",
                    "",
                    "| Requirement | Story | Acceptance Owner | Priority |",
                    "|---|---|---|---|",
                    "| FR-1 Product listing | US-1 | BA | High |",
                    "| FR-2 User auth | US-2 | BA | High |",
                    "| FR-3 Cart management | US-3 | BA | High |",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "acceptance_criteria.md").write_text(
            "\n".join(
                [
                    "# Acceptance Criteria",
                    "",
                    "## Product Listing",
                    "- Given products exist, when listing endpoint is called, then paginated items are returned.",
                    "## User Auth",
                    "- Given valid credentials, when login is requested, then token/session is returned.",
                    "## Cart",
                    "- Given product in stock, when add-to-cart is executed, then quantity and totals are updated.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_architect_improvement_docs(self, source_root: Path, improvements_root: Path) -> None:
        target = improvements_root / "architect"
        target.mkdir(parents=True, exist_ok=True)
        (target / "architecture.md").write_text(
            "\n".join(
                [
                    "# Architecture",
                    "",
                    "## Layered Design",
                    "- API Layer: controllers/routers + DTO validation",
                    "- Application Layer: use-cases and orchestration",
                    "- Domain Layer: entities, policies, business rules",
                    "- Infrastructure Layer: repositories, DB adapters, external clients",
                    "",
                    "## Module Boundaries",
                    "- catalog, users, cart, auth, observability",
                    "",
                    "## AuthZ/AuthN Strategy",
                    "- JWT/session auth, role guards, policy-based access checks",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "api_contracts.md").write_text(
            "\n".join(
                [
                    "# API Contracts",
                    "",
                    "- `GET /api/products` -> list products with filters/pagination.",
                    "- `POST /api/users/register` -> register user.",
                    "- `POST /api/auth/login` -> authenticate user.",
                    "- `GET /api/cart` -> retrieve current user cart.",
                    "- `POST /api/cart/items` -> add item to cart.",
                    "- `PATCH /api/cart/items/{id}` -> update quantity.",
                    "- `DELETE /api/cart/items/{id}` -> remove item.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "database_design.md").write_text(
            "\n".join(
                [
                    "# Database Design",
                    "",
                    "- `users(id, email, password_hash, role, created_at)`",
                    "- `products(id, sku, title, description, price, stock, status)`",
                    "- `carts(id, user_id, status, updated_at)`",
                    "- `cart_items(id, cart_id, product_id, qty, unit_price)`",
                    "- Foreign keys and unique indexes on SKU/email.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "deployment_architecture.md").write_text(
            "# Deployment Architecture\n\nDockerized frontend + backend + database + reverse proxy.\n",
            encoding="utf-8",
        )
        (target / "observability_plan.md").write_text(
            "# Observability Plan\n\nStructured logs, request tracing IDs, latency/error metrics per endpoint.\n",
            encoding="utf-8",
        )
        diagrams = target / "diagrams"
        diagrams.mkdir(parents=True, exist_ok=True)
        (diagrams / "service_flow.mmd").write_text(
            "flowchart LR\nClient --> API\nAPI --> App\nApp --> Domain\nApp --> Repo\nRepo --> DB\n",
            encoding="utf-8",
        )

    def _write_developer_improvement_docs(self, source_root: Path, improvements_root: Path) -> None:
        target = improvements_root / "developer"
        target.mkdir(parents=True, exist_ok=True)
        (target / "multi_pass_plan.md").write_text(
            "\n".join(
                [
                    "# Multi-Pass Development Plan",
                    "",
                    "1. Pass 1 - Scaffold architecture and contracts.",
                    "2. Pass 2 - Implement core product/user/cart functionality.",
                    "3. Pass 3 - Add validations and robust error handling.",
                    "4. Pass 4 - Refactor for modularity and maintainability.",
                    "5. Pass 5 - Generate unit/integration tests.",
                    "6. Pass 6 - Produce technical documentation updates.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "backend_depth_requirements.md").write_text(
            "\n".join(
                [
                    "# Backend Depth Requirements",
                    "",
                    "- Controllers + DTO validation per endpoint.",
                    "- Service layer with business rules (stock, user/cart ownership).",
                    "- Repository layer abstractions and persistence adapters.",
                    "- Error taxonomy + HTTP mapping + structured logging.",
                    "- Auth middleware and permission checks.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (target / "frontend_depth_requirements.md").write_text(
            "\n".join(
                [
                    "# Frontend Depth Requirements",
                    "",
                    "- Route-level screens (catalog, product detail, auth, cart).",
                    "- Reusable components and design tokens.",
                    "- Form validation and async loading/error states.",
                    "- API client integration and state handling.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_qa_improvement_docs(self, source_root: Path, improvements_root: Path) -> None:
        target = improvements_root / "qa"
        target.mkdir(parents=True, exist_ok=True)
        (target / "qa_report.md").write_text(
            "# QA Report\n\nCurrent QA output is superficial. Add API, UI, and edge-case evidence.\n",
            encoding="utf-8",
        )
        (target / "test_plan.md").write_text(
            "# Test Plan\n\nCover product listing, auth, cart workflows, and failure modes.\n",
            encoding="utf-8",
        )
        (target / "test_cases.md").write_text(
            "# Test Cases\n\n- Catalog filtering\n- Login failure\n- Cart stock validation\n",
            encoding="utf-8",
        )
        (target / "regression_scenarios.md").write_text(
            "# Regression Scenarios\n\nInclude user/cart state consistency and API contract regressions.\n",
            encoding="utf-8",
        )
        (target / "edge_case_matrix.md").write_text(
            "# Edge Case Matrix\n\nDocument empty carts, invalid product IDs, stock depletion, and concurrent updates.\n",
            encoding="utf-8",
        )
        (target / "coverage_summary.md").write_text(
            "# Coverage Summary\n\nRequire minimum coverage thresholds for critical flows.\n",
            encoding="utf-8",
        )
        (target / "api_tests").mkdir(parents=True, exist_ok=True)
        (target / "playwright_tests").mkdir(parents=True, exist_ok=True)

    def _write_docs_improvement_docs(self, source_root: Path, improvements_root: Path) -> None:
        target = improvements_root / "docs"
        target.mkdir(parents=True, exist_ok=True)
        for name, content in (
            ("README.md", "# README\n\nProject overview and quickstart.\n"),
            ("setup_guide.md", "# Setup Guide\n\nEnvironment setup, variables, and startup commands.\n"),
            ("deployment_guide.md", "# Deployment Guide\n\nContainer build/deploy steps.\n"),
            ("api_documentation.md", "# API Documentation\n\nEndpoint contracts and error schemas.\n"),
            ("architecture_overview.md", "# Architecture Overview\n\nLayers, modules, and key flows.\n"),
            ("troubleshooting.md", "# Troubleshooting\n\nCommon startup/runtime issues and fixes.\n"),
            ("onboarding_guide.md", "# Onboarding Guide\n\nHow new contributors run and extend the project.\n"),
        ):
            (target / name).write_text(content, encoding="utf-8")

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
        governance_validation = metadata.get("governance_validation", {}) if isinstance(metadata, dict) else {}
        if isinstance(governance_validation, dict) and governance_validation:
            report = governance_validation.get("report", {})
            warnings = governance_validation.get("warnings", ())
            if isinstance(report, dict) and report:
                (agent_root / "governance_report.json").write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            if isinstance(warnings, (list, tuple)) and warnings:
                (agent_root / "governance_warnings.md").write_text(
                    "# Governance Warnings\n\n" + "\n".join(f"- {str(item)}" for item in warnings),
                    encoding="utf-8",
                )
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
        if agent_name == "ba":
            intelligence = metadata.get("ba_intelligence", {}) if isinstance(metadata, dict) else {}
            documents = intelligence.get("documents", {}) if isinstance(intelligence, dict) else {}
            diagrams = intelligence.get("diagrams", {}) if isinstance(intelligence, dict) else {}
            if isinstance(documents, dict):
                for name, content in documents.items():
                    if not isinstance(name, str):
                        continue
                    target = agent_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content), encoding="utf-8")
            if isinstance(diagrams, dict):
                for name, content in diagrams.items():
                    if not isinstance(name, str):
                        continue
                    target = agent_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content), encoding="utf-8")
            self._finalize_ba_artifacts(agent_root)
        if agent_name == "architect":
            intelligence = metadata.get("architect_intelligence", {}) if isinstance(metadata, dict) else {}
            documents = intelligence.get("docs", {}) if isinstance(intelligence, dict) else {}
            diagrams = intelligence.get("diagrams", {}) if isinstance(intelligence, dict) else {}
            if isinstance(documents, dict):
                for name, content in documents.items():
                    if not isinstance(name, str):
                        continue
                    target = agent_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content), encoding="utf-8")
            if isinstance(diagrams, dict):
                for name, content in diagrams.items():
                    if not isinstance(name, str):
                        continue
                    target = agent_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(content), encoding="utf-8")
            self._finalize_architect_artifacts(agent_root)
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

    def _finalize_ba_artifacts(self, agent_root: Path) -> None:
        mvp_path = agent_root / "mvp_page_matrix.md"
        nav_path = agent_root / "navigation_structure.md"
        shell_path = agent_root / "application_shell.md"
        roadmap_path = agent_root / "roadmap_priorities.md"
        frontend_path = agent_root / "frontend_mvp_expectations.md"
        repaired: list[str] = []

        canonical = {
            "PUBLIC": ["Home", "About", "Contact", "Catalog", "Product Details", "Login", "Register"],
            "AUTH": ["Dashboard", "Profile", "Settings", "Orders", "Notifications"],
            "SYSTEM": ["Error pages", "Empty states", "Session expired", "Loading states"],
        }

        if not mvp_path.exists() or self._is_sparse_markdown(mvp_path.read_text(encoding="utf-8", errors="ignore")):
            lines = ["# MVP Page Matrix", "", "| Page | Category | Classification |", "|---|---|---|"]
            for category, pages in canonical.items():
                for page in pages:
                    classification = "Core MVP" if page in {"Home", "Login", "Register", "Catalog", "Product Details", "Cart", "Checkout", "Dashboard", "Profile", "Settings"} else ("Recommended MVP" if category != "SYSTEM" else "Recommended MVP")
                    lines.append(f"| {page} | {category} | {classification} |")
            lines.extend(["| Promotions/Coupons | AUTH | Future Enhancement |", "| Advanced Reports | AUTH | Future Enhancement |"])
            mvp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            repaired.append("mvp_page_matrix.md")

        if not nav_path.exists() or self._is_sparse_markdown(nav_path.read_text(encoding="utf-8", errors="ignore")):
            nav = [
                "# Navigation Structure",
                "",
                "## Public Navigation",
                *[f"- {item}" for item in canonical["PUBLIC"]],
                "",
                "## Authenticated Navigation",
                *[f"- {item}" for item in canonical["AUTH"]],
                "",
                "## Role-Aware Navigation",
                "- Customer: Catalog, Product Details, Cart, Checkout, Orders, Profile, Settings",
                "- Admin: Dashboard, Product Management, Orders, Reports, Settings",
                "",
                "## Fallback/Error Navigation",
                "- 401 -> Login with return URL",
                "- 403 -> Access denied",
                "- 404 -> Not found",
                "- 5xx -> Retry + support route",
                "",
                "## Session/Logout Behavior",
                "- Session expiry redirects to Login and preserves intended destination.",
                "- Logout clears session and returns to Home.",
            ]
            nav_path.write_text("\n".join(nav) + "\n", encoding="utf-8")
            repaired.append("navigation_structure.md")

        if not shell_path.exists() or self._is_sparse_markdown(shell_path.read_text(encoding="utf-8", errors="ignore")):
            shell = [
                "# Application Shell",
                "",
                "## Routing Hierarchy",
                "- Public: /, /about, /contact, /catalog, /products/:id, /login, /register",
                "- Protected: /dashboard, /profile, /settings, /orders, /cart, /checkout",
                "",
                "## Layout Composition",
                "- Public layout: header + footer + CTA nav",
                "- App layout: sidebar + topbar + breadcrumbs + toast notifications",
                "",
                "## Route Guards",
                "- Protected routes require active session.",
                "- Guest-only routes block authenticated users.",
                "",
                "## Session Restoration",
                "- Restore session on app bootstrap.",
                "- Expired session redirects to /login with next route.",
            ]
            shell_path.write_text("\n".join(shell) + "\n", encoding="utf-8")
            repaired.append("application_shell.md")

        if not roadmap_path.exists() or self._is_sparse_markdown(roadmap_path.read_text(encoding="utf-8", errors="ignore")):
            roadmap = [
                "# Roadmap Priorities",
                "",
                "## Core MVP",
                "- Home, Login/Register, Catalog, Product Details, Cart, Checkout",
                "- Dashboard, Profile, Settings, session handling, error/loading/empty states",
                "",
                "## Recommended MVP",
                "- Orders history, notifications, support/contact flows",
                "",
                "## Future Enhancement",
                "- Coupons/promotions engine",
                "- Advanced analytics and reporting",
                "- Recommendation system",
            ]
            roadmap_path.write_text("\n".join(roadmap) + "\n", encoding="utf-8")
            repaired.append("roadmap_priorities.md")

        if not frontend_path.exists() or self._is_sparse_markdown(frontend_path.read_text(encoding="utf-8", errors="ignore")):
            frontend_path.write_text(
                "# Frontend MVP Expectations\n\n- Reusable layouts (public/app)\n- Shared nav components\n- Validation + error UX\n- Loading + empty states\n- Toast notifications\n- Responsive behavior\n- Auth redirects and session persistence\n",
                encoding="utf-8",
            )
            repaired.append("frontend_mvp_expectations.md")

        index = self._build_ba_artifact_index(agent_root)
        (agent_root / "ba_artifact_index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        (agent_root / "artifact_completeness_report.md").write_text(
            self._build_ba_completeness_report(index=index, repaired_sections=repaired),
            encoding="utf-8",
        )
        (agent_root / "ba_quality_report.md").write_text(
            self._build_ba_quality_alignment_report(index=index, repaired_sections=repaired),
            encoding="utf-8",
        )

    def _finalize_architect_artifacts(self, agent_root: Path) -> None:
        required_docs = {
            "architecture.md": "# Architecture\n\nSystem overview pending finalization.\n",
            "module_decomposition.md": "# Module Decomposition\n\n## Identity\n- Responsibility: auth/session\n",
            "bounded_contexts.md": "# Bounded Contexts\n\n## Identity\n- Aggregate roots: User, Session\n",
            "api_contracts.md": "# API Contracts\n\n- GET /api/products\n- POST /api/checkout\n",
            "openapi_draft.yaml": (
                "openapi: 3.0.3\ninfo:\n  title: Solution API\n  version: 0.1.0\npaths:\n"
                "  /api/checkout:\n    post:\n      requestBody:\n        required: true\n        content:\n          application/json:\n            schema:\n              $ref: '#/components/schemas/CheckoutRequest'\n"
                "      responses:\n        '201':\n          description: Order created\n          content:\n            application/json:\n              schema:\n                $ref: '#/components/schemas/OrderResponse'\n"
                "        '422':\n          description: Validation error\ncomponents:\n  schemas:\n    CheckoutRequest:\n      type: object\n      properties:\n        address_id:\n          type: string\n    OrderResponse:\n      type: object\n      properties:\n        order_id:\n          type: string\n"
            ),
            "database_design.md": (
                "# Database Design\n\n## Tables\n- users(id, email, password_hash, role, status, created_at, updated_at, deleted_at)\n"
                "- products(id, sku, title, description, price, currency, status, created_at, updated_at)\n"
                "- carts(id, user_id, status, created_at, updated_at)\n- cart_items(id, cart_id, product_id, quantity, unit_price)\n"
                "- orders(id, user_id, status, amount_total, currency, created_at, updated_at)\n- order_items(id, order_id, product_id, quantity, unit_price)\n- payments(id, order_id, status, amount, created_at, updated_at)\n\n"
                "## Constraints\n- unique(users.email)\n- unique(products.sku)\n- cart_items unique(cart_id, product_id)\n- quantity > 0, price >= 0\n\n"
                "## Lifecycle\n- cart: ACTIVE -> CHECKED_OUT/EXPIRED\n- order: PENDING -> PAID/FAILED -> SHIPPED -> DELIVERED/CANCELLED\n"
            ),
            "frontend_architecture.md": "# Frontend Architecture\n\nRoute hierarchy and shared layouts.\n",
            "backend_architecture.md": (
                "# Backend Architecture\n\n## Layers\n- api (routers, middleware, schemas)\n- application (use cases, services, dto)\n- domain (entities, policies, repository interfaces)\n- infrastructure (db repos, external adapters)\n\n"
                "## Cross-cutting\n- validation strategy at DTO + domain levels\n- centralized error handling and response mapping\n- auth middleware and RBAC checks\n- structured logging and configuration boundaries\n"
            ),
            "event_flow_architecture.md": "# Event Flow Architecture\n\nDomain events and retry/idempotency.\n",
            "security_architecture.md": "# Security Architecture\n\nAuthN/AuthZ, validation, secrets handling.\n",
            "observability_plan.md": (
                "# Observability Plan\n\n## Logs\n- technical logs\n- audit logs\n- correlation IDs and trace IDs\n\n"
                "## Metrics\n- latency, error rate, throughput\n- checkout conversion, payment failure KPI\n\n"
                "## Traces and Health\n- distributed traces for checkout/auth\n- liveness/readiness endpoints\n- alert examples for p95 latency and 5xx spikes\n"
            ),
            "deployment_architecture.md": (
                "# Deployment Architecture\n\n## Services\n- frontend\n- backend\n- postgres\n- redis(optional)\n\n"
                "## Runtime\n- env vars for db/auth/provider keys\n- docker networking and persistent volumes\n- secrets via runtime injection\n- migration strategy before app rollout\n"
            ),
            "technical_risks.md": "# Technical Risks\n\n| Risk | Impact | Likelihood | Mitigation |\n|---|---|---|---|\n",
            "developer_handoff.md": (
                "# Developer Handoff\n\n## Modules\n- Identity, Catalog, Cart, Checkout, Orders, Admin\n\n"
                "## File Structure\n- backend/src/api, application, domain, infrastructure\n- frontend/src/routes, components, lib/api\n\n"
                "## Implement\n- endpoints: auth/products/cart/checkout/orders/profile\n- DTOs and entities for all order/cart flows\n- frontend routes and components for catalog/cart/checkout\n- validation rules and required tests (unit+integration)\n"
            ),
            "architect_quality_report.md": "# Architect Quality Report\n\n- Completeness score: 0/100\n",
        }
        required_diagrams = {
            "diagrams/system_context.mmd": "flowchart LR\nUser-->Frontend\nFrontend-->Backend\nBackend-->Database\n",
            "diagrams/container_diagram.mmd": "flowchart TD\nBrowser-->WebApp\nWebApp-->API\nAPI-->Postgres\n",
            "diagrams/module_dependencies.mmd": "flowchart LR\nIdentity-->Checkout\nCatalog-->Cart\nCart-->Orders\n",
            "diagrams/entity_relationships.mmd": "erDiagram\nUSERS ||--o{ ORDERS : places\n",
            "diagrams/checkout_sequence.mmd": "sequenceDiagram\nparticipant U as User\nU->>API: POST /checkout\n",
            "diagrams/auth_sequence.mmd": "sequenceDiagram\nUser->>API: POST /auth/login\n",
            "diagrams/deployment_diagram.mmd": "flowchart LR\nIngress-->Frontend\nIngress-->Backend\nBackend-->DB\n",
        }
        required_adrs = {
            "adr/0001-architecture-style.md": "# ADR 0001 - Architecture Style\n\nContext\nDecision\nConsequences\nAlternatives\n",
            "adr/0002-auth-session-strategy.md": "# ADR 0002 - Auth/Session Strategy\n\nContext\nDecision\nConsequences\nAlternatives\n",
            "adr/0003-database-design.md": "# ADR 0003 - Database Design\n\nContext\nDecision\nConsequences\nAlternatives\n",
            "adr/0004-frontend-routing.md": "# ADR 0004 - Frontend Routing\n\nContext\nDecision\nConsequences\nAlternatives\n",
            "adr/0005-error-handling.md": "# ADR 0005 - Error Handling\n\nContext\nDecision\nConsequences\nAlternatives\n",
        }

        repaired: list[str] = []
        for relative, template in {**required_docs, **required_diagrams, **required_adrs}.items():
            target = agent_root / relative
            existing = target.read_text(encoding="utf-8", errors="ignore") if target.exists() else ""
            if (not target.exists()) or self._is_sparse_markdown(existing):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(template, encoding="utf-8")
                repaired.append(relative)

        index = self._build_architect_artifact_index(agent_root)
        (agent_root / "architect_artifact_index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        (agent_root / "architect_quality_report.md").write_text(
            self._build_architect_quality_report(index=index, repaired_sections=repaired),
            encoding="utf-8",
        )

    def _build_architect_artifact_index(self, agent_root: Path) -> dict[str, Any]:
        def exists(rel: str) -> bool:
            return (agent_root / rel).exists()
        def read(rel: str) -> str:
            return (agent_root / rel).read_text(encoding="utf-8", errors="ignore") if exists(rel) else ""
        def depth_score(text: str, *, required_tokens: tuple[str, ...], min_chars: int) -> int:
            value = (text or "").strip()
            if not value:
                return 0
            score = 35 if len(value) >= min_chars else int(35 * (len(value) / max(1, min_chars)))
            lowered = value.lower()
            token_hits = sum(1 for token in required_tokens if token in lowered)
            score += min(45, token_hits * max(1, int(45 / max(1, len(required_tokens)))))
            if any(placeholder in lowered for placeholder in ("todo", "placeholder", "tbd", "pending finalization")):
                score -= 25
            if len(value.splitlines()) < 8:
                score -= 10
            return max(0, min(100, score))

        api_text = read("api_contracts.md")
        db_text = read("database_design.md")
        backend_text = read("backend_architecture.md")
        observability_text = read("observability_plan.md")
        deployment_text = read("deployment_architecture.md")
        handoff_text = read("developer_handoff.md")
        openapi_text = read("openapi_draft.yaml")
        return {
            "artifacts_present": {
                "architecture": exists("architecture.md"),
                "module_decomposition": exists("module_decomposition.md"),
                "bounded_contexts": exists("bounded_contexts.md"),
                "api_contracts": exists("api_contracts.md"),
                "openapi": exists("openapi_draft.yaml"),
                "database_design": exists("database_design.md"),
                "frontend_architecture": exists("frontend_architecture.md"),
                "backend_architecture": exists("backend_architecture.md"),
                "event_flow_architecture": exists("event_flow_architecture.md"),
                "security_architecture": exists("security_architecture.md"),
                "observability_plan": exists("observability_plan.md"),
                "deployment_architecture": exists("deployment_architecture.md"),
                "technical_risks": exists("technical_risks.md"),
                "developer_handoff": exists("developer_handoff.md"),
                "quality_report": exists("architect_quality_report.md"),
            },
            "diagram_files": sorted(str(path.relative_to(agent_root)).replace("\\", "/") for path in (agent_root / "diagrams").glob("*.mmd")) if (agent_root / "diagrams").exists() else [],
            "adr_files": sorted(str(path.relative_to(agent_root)).replace("\\", "/") for path in (agent_root / "adr").glob("*.md")) if (agent_root / "adr").exists() else [],
            "api_endpoint_count": sum(1 for line in api_text.splitlines() if line.strip().startswith("- ") and "/" in line),
            "db_entity_mentions": sum(1 for entity in ("users", "products", "inventory", "carts", "orders", "payments") if entity in db_text.lower()),
            "depth_scores": {
                "openapi": depth_score(openapi_text, required_tokens=("components:", "schemas:", "requestbody", "responses:", "security"), min_chars=1200),
                "database_design": depth_score(db_text, required_tokens=("primary key", "foreign key", "index", "constraint", "audit", "soft delete"), min_chars=900),
                "backend_architecture": depth_score(backend_text, required_tokens=("api", "application", "domain", "infrastructure", "middleware", "validation", "logging"), min_chars=1000),
                "observability_plan": depth_score(observability_text, required_tokens=("logs", "audit", "metrics", "traces", "health", "alert", "correlation"), min_chars=700),
                "deployment_architecture": depth_score(deployment_text, required_tokens=("docker", "environment", "network", "volume", "secrets", "migration"), min_chars=700),
                "developer_handoff": depth_score(handoff_text, required_tokens=("modules", "file structure", "endpoints", "dto", "entities", "routes", "tests"), min_chars=900),
            },
        }

    def _build_architect_quality_report(self, *, index: dict[str, Any], repaired_sections: list[str]) -> str:
        checks = index.get("artifacts_present", {})
        depth_scores = index.get("depth_scores", {}) if isinstance(index.get("depth_scores", {}), dict) else {}
        check_score = int((sum(1 for v in checks.values() if v) / max(1, len(checks))) * 100) if isinstance(checks, dict) else 0
        api_score = min(100, int(index.get("api_endpoint_count", 0)) * 6 + int(depth_scores.get("openapi", 0) * 0.4))
        db_score = min(100, int(index.get("db_entity_mentions", 0)) * 8 + int(depth_scores.get("database_design", 0) * 0.5))
        diagram_score = min(100, len(index.get("diagram_files", [])) * 14)
        adr_score = min(100, len(index.get("adr_files", [])) * 20)
        backend_score = int(depth_scores.get("backend_architecture", 0))
        observability_score = int(depth_scores.get("observability_plan", 0))
        deployment_score = int(depth_scores.get("deployment_architecture", 0))
        handoff_score = int(depth_scores.get("developer_handoff", 0))
        warnings: list[str] = []
        for key, value in depth_scores.items():
            if int(value) < 65:
                warnings.append(f"{key} depth is low ({value}/100).")
        lines = [
            "# Architect Quality Report",
            "",
            f"- Module completeness: {int((check_score * 0.4) + (backend_score * 0.6))}/100",
            f"- API completeness: {api_score}/100",
            f"- DB completeness: {db_score}/100",
            f"- Frontend architecture completeness: {80 if checks.get('frontend_architecture') else 30}/100",
            f"- Backend architecture completeness: {backend_score}/100",
            f"- Security completeness: {80 if checks.get('security_architecture') else 40}/100",
            f"- Observability completeness: {observability_score}/100",
            f"- Deployment readiness: {deployment_score}/100",
            f"- Developer handoff readiness: {handoff_score}/100",
            "",
            "## Repaired Sections",
        ]
        lines.extend(f"- {name}" for name in (repaired_sections or ["none"]))
        lines.extend(
            [
                "",
                f"- Diagram coverage score: {diagram_score}/100",
                f"- ADR coverage score: {adr_score}/100",
                "",
                "## Depth Warnings",
            ]
        )
        lines.extend(f"- {warning}" for warning in (warnings or ["none"]))
        return "\n".join(lines) + "\n"

    def _is_sparse_markdown(self, text: str) -> bool:
        cleaned = (text or "").strip()
        if len(cleaned) < 80:
            return True
        non_header_lines = [line for line in cleaned.splitlines() if line.strip() and not line.strip().startswith("#")]
        if len(non_header_lines) < 4:
            return True
        placeholder_hits = sum(
            1
            for line in non_header_lines
            if any(token in line.lower() for token in ("todo", "insert", "placeholder", "tbd"))
        )
        return placeholder_hits > 0 and len(non_header_lines) <= 8

    def _build_ba_artifact_index(self, agent_root: Path) -> dict[str, Any]:
        def read(name: str) -> str:
            path = agent_root / name
            return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""

        mvp_text = read("mvp_page_matrix.md")
        nav_text = read("navigation_structure.md")
        shell_text = read("application_shell.md")
        lifecycle_text = read("user_lifecycle.md")
        permissions_text = read("permissions_matrix.md")
        validation_text = read("validation_rules.md")
        states_text = read("state_machines.md")
        events_text = read("business_events.md")
        entities_text = read("domain_entities.md")

        index = {
            "pages": {
                "home": "home" in mvp_text.lower() or "home" in nav_text.lower() or "home" in shell_text.lower(),
                "dashboard": "dashboard" in mvp_text.lower() or "dashboard" in nav_text.lower() or "dashboard" in shell_text.lower(),
                "profile": "profile" in mvp_text.lower() or "profile" in nav_text.lower() or "profile" in shell_text.lower(),
                "settings": "settings" in mvp_text.lower() or "settings" in nav_text.lower() or "settings" in shell_text.lower(),
            },
            "navigation_entries": [line.strip("- ").strip() for line in nav_text.splitlines() if line.strip().startswith("-")][:50],
            "entities": [line.replace("## ", "").strip() for line in entities_text.splitlines() if line.startswith("## ")],
            "states": [line.replace("## ", "").strip() for line in states_text.splitlines() if line.startswith("## ")],
            "permissions": [line for line in permissions_text.splitlines() if line.startswith("| ")][:20],
            "validations": [line.strip("- ").strip() for line in validation_text.splitlines() if line.strip().startswith("-")][:30],
            "flows": [line.replace("## ", "").strip() for line in read("functional_flows.md").splitlines() if line.startswith("## ")],
            "events": [line.replace("## ", "").strip() for line in events_text.splitlines() if line.startswith("## ")],
            "lifecycle_present": "session lifecycle" in lifecycle_text.lower() or "onboarding" in lifecycle_text.lower(),
        }
        return index

    def _build_ba_completeness_report(self, *, index: dict[str, Any], repaired_sections: list[str]) -> str:
        checks = {
            "mvp_pages_inferred": all(index["pages"].values()),
            "navigation_populated": len(index["navigation_entries"]) >= 8,
            "entities_modeled": len(index["entities"]) >= 3,
            "states_modeled": len(index["states"]) >= 2,
            "permissions_modeled": len(index["permissions"]) >= 2,
            "validations_modeled": len(index["validations"]) >= 3,
            "flows_modeled": len(index["flows"]) >= 1,
            "events_modeled": len(index["events"]) >= 2,
            "lifecycle_modeled": bool(index["lifecycle_present"]),
        }
        score = round((sum(1 for ok in checks.values() if ok) / max(1, len(checks))) * 100, 2)
        lines = ["# Artifact Completeness Report", "", f"- Completeness score: {score}%", ""]
        lines.append("## Checks")
        lines.extend(f"- {name}: {'ok' if ok else 'missing'}" for name, ok in checks.items())
        lines.extend(["", "## Repaired Sections"])
        lines.extend(f"- {name}" for name in (repaired_sections or ["none"]))
        return "\n".join(lines) + "\n"

    def _build_ba_quality_alignment_report(self, *, index: dict[str, Any], repaired_sections: list[str]) -> str:
        warnings: list[str] = []
        if not index["pages"]["home"]:
            warnings.append("Missing Home/Landing page inference.")
        if not index["pages"]["dashboard"]:
            warnings.append("Missing Dashboard inference.")
        if not index["pages"]["profile"]:
            warnings.append("Missing Profile inference.")
        if not index["pages"]["settings"]:
            warnings.append("Missing Settings inference.")
        if len(index["navigation_entries"]) < 8:
            warnings.append("Navigation hierarchy is shallow.")
        if not index["lifecycle_present"]:
            warnings.append("User lifecycle/session flow missing.")
        if len(index["entities"]) < 3:
            warnings.append("Entity modeling is shallow.")
        score = max(0, 100 - len(warnings) * 12)
        lines = [
            "# BA Quality Report",
            "",
            f"- Completeness score: {score}/100",
            f"- MVP completeness score: {100 if all(index['pages'].values()) else 60}/100",
            f"- Navigation completeness score: {min(100, len(index['navigation_entries']) * 8)}/100",
            f"- Lifecycle completeness score: {100 if index['lifecycle_present'] else 40}/100",
            "",
            "## Inferred Sections",
            f"- Repaired sections count: {len(repaired_sections)}",
            "",
            "## Governance Warnings",
        ]
        lines.extend(f"- {warning}" for warning in (warnings or ["none"]))
        lines.extend(["", "## Consistency Signals", "- pages align with navigation and shell", "- lifecycle references auth/session flows"])
        return "\n".join(lines) + "\n"

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
