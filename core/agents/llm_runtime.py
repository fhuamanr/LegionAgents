"""LLM-backed executable agents for the delivery workflow."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any
import os

from pydantic import BaseModel

from core.agents.model_clients import OpenAIChatModelClient
from core.agents.ba_intelligence import build_ba_intelligence_bundle
from core.agents.architect_intelligence import build_architect_bundle
from core.agents.runtime import AgentModelClient
from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.outputs import (
    ArchitectOutput,
    BARequirementsOutput,
    DeveloperOutput,
    DocsOutput,
    OutputContractKind,
    PullRequestOutput,
    QAOutput,
)
from core.contracts.repository import (
    BranchCreationRequest,
    CommitGenerationRequest,
    RepositoryCloneRequest,
    RepositoryRuntimeResult,
)
from core.repository import RepositoryRuntime
from core.runtime.agent import BaseAgent
from core.runtime.context import GovernanceRuntimeContextAssembler
from core.runtime.models import RuntimeExecutionContext
from core.runtime.models import RuntimeAgentConfig
from core.runtime.retry import RetryEngine, RetryPolicy
from core.runtime.validation import PydanticOutputValidator


class LLMStructuredAgentRuntime(BaseAgent[BaseModel]):
    """Reusable real LLM runtime for one isolated specialized agent."""

    def __init__(
        self,
        *,
        config: RuntimeAgentConfig,
        output_model: type[BaseModel],
        artifact_kind: ArtifactKind,
        model_client: AgentModelClient,
        retry_engine: RetryEngine | None = None,
    ) -> None:
        super().__init__(
            config=config,
            output_validator=PydanticOutputValidator(output_model),
            context_assembler=GovernanceRuntimeContextAssembler(),
            retry_engine=retry_engine or RetryEngine(RetryPolicy(max_attempts=2)),
        )
        self._model_client = model_client
        self._artifact_kind = artifact_kind

    async def invoke(self, context: Any) -> str:
        local_safe_mode = bool(context.request.metadata.get("local_lm_studio_safe_mode", False))
        token_callback = context.request.metadata.get("token_callback")
        if local_safe_mode:
            if hasattr(self._model_client, "complete_for_runtime"):
                return await self._model_client.complete_for_runtime(context)  # type: ignore[attr-defined]
            return await self._model_client.complete(context.prompt_messages)
        if callable(token_callback) and hasattr(self._model_client, "stream_for_runtime"):
            chunks: list[str] = []
            async for chunk in self._model_client.stream_for_runtime(context):  # type: ignore[attr-defined]
                chunks.append(chunk)
                await token_callback(
                    context.request.workflow_id,
                    context.request.execution_id,
                    self.config.name,
                    chunk,
                )
            return "".join(chunks)
        if hasattr(self._model_client, "complete_for_runtime"):
            return await self._model_client.complete_for_runtime(context)  # type: ignore[attr-defined]
        if callable(token_callback) and hasattr(self._model_client, "stream_complete"):
            chunks: list[str] = []
            async for chunk in self._model_client.stream_complete(context.prompt_messages):  # type: ignore[attr-defined]
                chunks.append(chunk)
                await token_callback(
                    context.request.workflow_id,
                    context.request.execution_id,
                    self.config.name,
                    chunk,
                )
            return "".join(chunks)
        return await self._model_client.complete(context.prompt_messages)

    async def build_artifacts(
        self,
        request: AgentExecutionRequest,
        output: BaseModel,
    ) -> tuple[Artifact, ...]:
        contract_kind = getattr(output, "contract_kind", OutputContractKind.GENERIC)
        return (
            Artifact(
                id=f"{self.config.name}-{request.execution_id}",
                kind=self._artifact_kind,
                name=f"{self.config.name} structured output",
                producer_agent=self.config.name,
                content=output.model_dump_json(indent=2),
                metadata={"contract_kind": str(contract_kind)},
            ),
        )

    def result_metadata(self, output: BaseModel) -> dict[str, object]:
        metadata: dict[str, object] = {}
        contract_kind = getattr(output, "contract_kind", None)
        if contract_kind is not None:
            metadata["contract_kind"] = str(contract_kind)
        if isinstance(output, QAOutput):
            metadata["route_signal"] = "continue" if output.passed else "reject"
            metadata["passed"] = output.passed
        return metadata


class BusinessAnalystAgentRuntime(LLMStructuredAgentRuntime):
    """BA runtime with advanced functional-analysis intelligence outputs."""

    async def build_artifacts(
        self,
        request: AgentExecutionRequest,
        output: BaseModel,
    ) -> tuple[Artifact, ...]:
        base = await super().build_artifacts(request, output)
        if not isinstance(output, BARequirementsOutput):
            return base
        bundle = build_ba_intelligence_bundle(
            task=request.task,
            structured_output=output.model_dump(mode="json"),
        )
        artifacts: list[Artifact] = list(base)
        for name, content in bundle["documents"].items():
            artifacts.append(
                Artifact(
                    id=f"ba-doc-{request.execution_id}-{name}",
                    kind=ArtifactKind.DOCUMENTATION,
                    name=name,
                    producer_agent=self.config.name,
                    content=content,
                )
            )
        for name, content in bundle["diagrams"].items():
            artifacts.append(
                Artifact(
                    id=f"ba-diagram-{request.execution_id}-{name}",
                    kind=ArtifactKind.DIAGRAM,
                    name=name,
                    producer_agent=self.config.name,
                    content=content,
                )
            )
        return tuple(artifacts)

    async def _execute_once(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        result = await super()._execute_once(request)
        if result.status != AgentStatus.COMPLETED:
            return result
        structured = result.metadata.get("structured_output", {}) if isinstance(result.metadata, dict) else {}
        if not isinstance(structured, dict):
            return result
        bundle = build_ba_intelligence_bundle(task=request.task, structured_output=structured)
        updated = dict(result.metadata)
        updated["ba_intelligence"] = bundle
        return result.model_copy(update={"metadata": updated})


class SolutionArchitectAgentRuntime(LLMStructuredAgentRuntime):
    """Architect runtime that converts finalized BA artifacts into technical blueprints."""

    async def build_artifacts(
        self,
        request: AgentExecutionRequest,
        output: BaseModel,
    ) -> tuple[Artifact, ...]:
        base = await super().build_artifacts(request, output)
        if not isinstance(output, ArchitectOutput):
            return base
        bundle = build_architect_bundle(
            task=request.task,
            ba_index=self._extract_ba_index(request),
            ba_docs=self._extract_ba_docs(request),
            structured_output=output.model_dump(mode="json"),
        )
        artifacts: list[Artifact] = list(base)
        for name, content in bundle.get("docs", {}).items():
            artifacts.append(
                Artifact(
                    id=f"architect-doc-{request.execution_id}-{name}",
                    kind=ArtifactKind.ARCHITECTURE,
                    name=name,
                    producer_agent=self.config.name,
                    content=str(content),
                )
            )
        for name, content in bundle.get("diagrams", {}).items():
            artifacts.append(
                Artifact(
                    id=f"architect-diagram-{request.execution_id}-{name}",
                    kind=ArtifactKind.DIAGRAM,
                    name=name,
                    producer_agent=self.config.name,
                    content=str(content),
                )
            )
        return tuple(artifacts)

    async def _execute_once(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        result = await super()._execute_once(request)
        if result.status != AgentStatus.COMPLETED:
            return result
        structured = result.metadata.get("structured_output", {}) if isinstance(result.metadata, dict) else {}
        if not isinstance(structured, dict):
            return result
        bundle = build_architect_bundle(
            task=request.task,
            ba_index=self._extract_ba_index(request),
            ba_docs=self._extract_ba_docs(request),
            structured_output=structured,
        )
        updated = dict(result.metadata)
        updated["architect_intelligence"] = bundle
        return result.model_copy(update={"metadata": updated})

    def _extract_ba_docs(self, request: AgentExecutionRequest) -> dict[str, str]:
        docs: dict[str, str] = {}
        for artifact in request.upstream_artifacts:
            producer = str(artifact.producer_agent or "").lower()
            if producer != "ba":
                continue
            name = str(artifact.name or "").strip()
            if name:
                docs[name] = str(artifact.content or "")
        return docs

    def _extract_ba_index(self, request: AgentExecutionRequest) -> dict[str, Any]:
        for artifact in request.upstream_artifacts:
            producer = str(artifact.producer_agent or "").lower()
            if producer != "ba":
                continue
            name = str(artifact.name or "").strip().lower()
            if not name.endswith("ba_artifact_index.json"):
                continue
            try:
                payload = json.loads(str(artifact.content or "{}"))
            except json.JSONDecodeError:
                return {}
            return payload if isinstance(payload, dict) else {}
        return {}


class DeveloperRepositoryAgentRuntime(LLMStructuredAgentRuntime):
    """Developer agent runtime that applies generated changes to real repositories."""

    def __init__(
        self,
        *,
        config: RuntimeAgentConfig,
        model_client: AgentModelClient,
        repository_runtime: RepositoryRuntime | None = None,
    ) -> None:
        super().__init__(
            config=config,
            output_model=DeveloperOutput,
            artifact_kind=ArtifactKind.SOURCE_CODE,
            model_client=model_client,
        )
        self._repository_runtime = repository_runtime or RepositoryRuntime()

    async def _execute_once(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        resolved_inputs, resolution_report, missing_required = self._resolve_architect_inputs(request)
        if missing_required:
            report_content = self._render_resolution_report(resolution_report)
            return AgentExecutionResult(
                execution_id=request.execution_id,
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                summary="Developer input resolution failed before LLM execution.",
                errors=(
                    "schema_contract_error: developer_input_missing_required_architect_artifacts: "
                    + ", ".join(missing_required),
                ),
                artifacts=(
                    Artifact(
                        id=f"developer-input-resolution-{request.execution_id}",
                        kind=ArtifactKind.GENERIC,
                        name="developer_input_resolution_report.md",
                        producer_agent=self.config.name,
                        content=report_content,
                    ),
                ),
                metadata={
                    "error_type": "schema_contract_error",
                    "retry_allowed": False,
                    "developer_input_resolution": resolution_report,
                },
            )
        agent_context = await self._context_assembler.assemble(request, self.config)
        tool_names = await self._tool_registry.names()
        runtime_context = RuntimeExecutionContext(
            request=request,
            agent_config=self.config,
            agent_context=agent_context,
            tools=tool_names,
        )
        prompt_messages = await self._prompt_builder.build(runtime_context)
        runtime_context = runtime_context.model_copy(update={"prompt_messages": prompt_messages})
        structured_output, raw_output, pass_records = await self._run_multipass_development(runtime_context, request)
        structured_output = self._augment_with_incremental_project(request, structured_output, resolved_inputs)
        governance_warning: str | None = None
        try:
            await self._enforce_governance_output(runtime_context, raw_output)
            await self._enforce_governance_output(runtime_context, raw_output, structured_output)
        except ValueError as exc:
            text = str(exc).lower()
            critical_markers = ("secret", "credential", "private key", "malicious", "rm -rf", "token=")
            if any(marker in text for marker in critical_markers):
                raise
            governance_warning = str(exc)
        if not isinstance(structured_output, DeveloperOutput):
            raise TypeError("Developer runtime must return DeveloperOutput.")

        repository_result = await self._execute_repository_changes(request, structured_output)
        artifacts = await self.build_artifacts(request, structured_output)
        if repository_result is not None:
            artifacts = artifacts + self._repository_artifacts(request, repository_result)
        artifacts = artifacts + tuple(
            Artifact(
                id=f"developer-pass-{request.execution_id}-{record['pass']}",
                kind=ArtifactKind.GENERIC,
                name=f"pass_{record['pass']}_raw_output.md",
                producer_agent=self.config.name,
                content=str(record.get("raw_output", "")),
                metadata={
                    "pass": record["pass"],
                    "phase": record["phase"],
                    "structured_output": record.get("structured_output", {}),
                },
            )
            for record in pass_records
        )

        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self.config.name,
            status=AgentStatus.COMPLETED,
            summary=self.summarize(structured_output),
            artifacts=artifacts,
            metadata={
                "prompt_message_count": len(prompt_messages),
                "context_document_count": agent_context.metadata.get("document_count", 0),
                "context_engineering": agent_context.metadata.get("context_engineering", {}),
                "structured_output": structured_output.model_dump(mode="json"),
                "raw_output": raw_output,
                "pass_records": pass_records,
                "governance_warning": governance_warning,
                "developer_input_resolution": resolution_report,
                **self.result_metadata(structured_output),
                **self._repository_metadata(repository_result),
            },
        )

    async def _run_multipass_development(
        self,
        runtime_context: RuntimeExecutionContext,
        request: AgentExecutionRequest,
    ) -> tuple[DeveloperOutput, str, list[dict[str, Any]]]:
        local_safe_mode = bool(request.metadata.get("local_lm_studio_safe_mode", False))
        configured_passes = int(request.metadata.get("developer_passes", 6))
        pass_count = max(1, min(configured_passes, 6 if not local_safe_mode else 2))
        phases = (
            "Pass 1: scaffold modules and contracts.",
            "Pass 2: implement core business functionality.",
            "Pass 3: add validations and error handling.",
            "Pass 4: improve/refactor design quality.",
            "Pass 5: generate/expand tests.",
            "Pass 6: provide documentation-facing technical notes.",
        )
        merged_payload: dict[str, Any] = {}
        all_raw_outputs: list[str] = []
        pass_records: list[dict[str, Any]] = []
        for index in range(pass_count):
            phase = phases[index]
            user_prompt = runtime_context.prompt_messages[1].content + f"\n\n# Development Phase\n{phase}\n"
            if merged_payload:
                user_prompt += (
                    "\n# Previous Pass Summary (carry forward and improve)\n"
                    + json.dumps(
                        {
                            "summary": merged_payload.get("summary"),
                            "code_changes": merged_payload.get("code_changes", [])[:3],
                            "tests": merged_payload.get("tests", [])[:3],
                        },
                        ensure_ascii=False,
                    )
                )
            phase_context = runtime_context.model_copy(
                update={
                    "prompt_messages": (
                        runtime_context.prompt_messages[0],
                        runtime_context.prompt_messages[1].model_copy(update={"content": user_prompt}),
                    )
                }
            )
            phase_raw = await self.invoke(phase_context)
            all_raw_outputs.append(phase_raw)
            phase_structured = await self._output_validator.validate(phase_raw, strategy="developer_sections")
            if not isinstance(phase_structured, DeveloperOutput):
                continue
            pass_records.append(
                {
                    "pass": index + 1,
                    "phase": phase,
                    "raw_output": phase_raw,
                    "structured_output": phase_structured.model_dump(mode="json"),
                }
            )
            merged_payload = self._merge_developer_outputs(merged_payload, phase_structured.model_dump(mode="json"))
        if not merged_payload:
            fallback = await self._output_validator.validate(all_raw_outputs[-1] if all_raw_outputs else "", strategy="developer_sections")
            assert isinstance(fallback, DeveloperOutput)
            pass_records.append(
                {
                    "pass": 1,
                    "phase": "fallback",
                    "raw_output": all_raw_outputs[-1] if all_raw_outputs else "",
                    "structured_output": fallback.model_dump(mode="json"),
                }
            )
            return fallback, "\n\n".join(all_raw_outputs), pass_records
        merged_structured = DeveloperOutput.model_validate(merged_payload)
        return merged_structured, "\n\n".join(all_raw_outputs), pass_records

    def _augment_with_incremental_project(self, request: AgentExecutionRequest, output: DeveloperOutput, resolved_inputs: dict[str, str]) -> DeveloperOutput:
        payload = output.model_dump(mode="json")
        metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        upstream = resolved_inputs
        implementation_mode = str(request.metadata.get("developer_mode", "implement_core")).strip().lower() or "implement_core"
        local_safe_mode = bool(request.metadata.get("local_lm_studio_safe_mode", False))
        passes_executed = self._passes_for_mode(implementation_mode, local_safe_mode)
        generated = self._generated_project_files(upstream, mode=implementation_mode)

        code_changes = list(payload.get("code_changes", [])) if isinstance(payload.get("code_changes", []), list) else []
        existing_paths = {str(item.get("path", "")) for item in code_changes if isinstance(item, dict)}
        for path, content in generated["files"].items():
            if path in existing_paths:
                continue
            code_changes.append(
                {
                    "path": path,
                    "change_type": "create",
                    "description": f"Generated by developer incremental engine: {path}",
                    "content": content,
                }
            )
            existing_paths.add(path)
        payload["code_changes"] = code_changes[:160]

        tests = list(payload.get("tests", [])) if isinstance(payload.get("tests", []), list) else []
        existing_test_paths = {str(item.get("path", "")) for item in tests if isinstance(item, dict)}
        for path, content in generated["tests"].items():
            if path in existing_test_paths:
                continue
            tests.append(
                {
                    "path": path,
                    "test_type": "unit" if "playwright" not in path else "e2e",
                    "description": f"Generated test: {path}",
                    "content": content,
                }
            )
            existing_test_paths.add(path)
        payload["tests"] = tests[:80]

        metadata.update(
            {
                "passes_executed": passes_executed,
                "generated_files": sorted(generated["files"].keys()),
                "matrices": [
                    "developer/generated_project/api_implementation_matrix.md",
                    "developer/generated_project/database_implementation_matrix.md",
                    "developer/generated_project/frontend_route_matrix.md",
                ],
                "quality_report": generated["quality_report"],
                "handoff": generated["qa_handoff"],
                "implementation_mode": implementation_mode,
            }
        )
        payload["metadata"] = metadata
        if not str(payload.get("summary", "")).strip():
            payload["summary"] = "Incremental implementation package generated from architect handoff."
        return DeveloperOutput.model_validate(payload)

    def _validate_required_architect_inputs(self, docs: dict[str, str]) -> None:
        required = (
            "developer_handoff.md",
            "openapi_draft.yaml",
            "backend_architecture.md",
            "frontend_architecture.md",
            "database_design.md",
            "api_contracts.md",
            "module_decomposition.md",
        )
        missing = [name for name in required if not str(docs.get(name, "")).strip() or len(str(docs.get(name, "")).strip()) < 24]
        if missing:
            raise ValueError(
                "schema_contract_error: developer_input_missing_required_architect_artifacts: "
                + ", ".join(missing)
            )

    def _resolve_architect_inputs(self, request: AgentExecutionRequest) -> tuple[dict[str, str], dict[str, Any], list[str]]:
        required = (
            "developer_handoff.md",
            "openapi_draft.yaml",
            "backend_architecture.md",
            "frontend_architecture.md",
            "database_design.md",
            "api_contracts.md",
            "module_decomposition.md",
        )
        aliases: dict[str, tuple[str, ...]] = {
            "developer_handoff.md": ("handoff/developer_handoff.md", "developer_handoff.md"),
            "openapi_draft.yaml": ("api/openapi_draft.yaml", "openapi_draft.yaml"),
            "backend_architecture.md": ("backend/backend_architecture.md", "backend_architecture.md"),
            "frontend_architecture.md": ("frontend/frontend_architecture.md", "frontend_architecture.md"),
            "database_design.md": ("database/database_design.md", "database_design.md"),
            "api_contracts.md": ("api/api_contracts.md", "api_contracts.md"),
            "module_decomposition.md": ("architecture/module_decomposition.md", "module_decomposition.md"),
        }
        resolved: dict[str, str] = {}
        report: dict[str, Any] = {"workflow_id": str(request.workflow_id), "required": [], "source_index_used": False}

        upstream = self._extract_architect_docs(request)
        for name in required:
            value = str(upstream.get(name, "")).strip()
            if value:
                resolved[name] = value
                report["required"].append({"name": name, "resolved_path": f"upstream:{name}", "size_bytes": len(value.encode('utf-8')), "missing_reason": "", "preview": value[:120]})
            else:
                report["required"].append({"name": name, "resolved_path": "", "size_bytes": 0, "missing_reason": "not found in upstream artifacts", "preview": ""})

        artifacts_root = Path(os.getenv("ARTIFACT_ROOT", "data/artifacts")).resolve()
        architect_root = artifacts_root / str(request.workflow_id) / "architect"
        if architect_root.exists():
            index_path = architect_root / "architect_artifact_index.json"
            index_data: dict[str, Any] = {}
            if index_path.exists():
                try:
                    index_data = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
                    report["source_index_used"] = True
                except json.JSONDecodeError:
                    index_data = {}
            indexed_map: dict[str, str] = {}
            artifacts_list = index_data.get("artifacts", []) if isinstance(index_data, dict) else []
            if isinstance(artifacts_list, list):
                for item in artifacts_list:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    path = str(item.get("path", "")).strip()
                    if name and path:
                        indexed_map[name] = path
            for entry in report["required"]:
                name = entry["name"]
                if name in resolved:
                    continue
                candidate_rel_paths = []
                if name in indexed_map:
                    candidate_rel_paths.append(indexed_map[name].replace("architect/", "", 1))
                candidate_rel_paths.extend(list(aliases.get(name, (name,))))
                found_path = ""
                found_content = ""
                for rel in candidate_rel_paths:
                    target = architect_root / rel
                    if target.exists() and target.is_file():
                        content = target.read_text(encoding="utf-8", errors="ignore")
                        if content.strip():
                            found_path = str(target)
                            found_content = content
                            break
                if found_content:
                    resolved[name] = found_content
                    entry["resolved_path"] = found_path
                    entry["size_bytes"] = len(found_content.encode("utf-8"))
                    entry["missing_reason"] = ""
                    entry["preview"] = found_content[:120]
                elif not entry["missing_reason"]:
                    entry["missing_reason"] = "not found in architect artifact directory"

        missing = [name for name in required if not resolved.get(name, "").strip()]
        return resolved, report, missing

    def _render_resolution_report(self, report: dict[str, Any]) -> str:
        lines = ["# Developer Input Resolution Report", ""]
        lines.append(f"- Workflow ID: {report.get('workflow_id', '')}")
        lines.append(f"- Source index used: {bool(report.get('source_index_used', False))}")
        lines.append("")
        lines.append("| Required Artifact | Resolved Path | Bytes | Missing Reason |")
        lines.append("|---|---|---:|---|")
        for item in report.get("required", []):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('name','')} | {item.get('resolved_path','')} | {item.get('size_bytes',0)} | {item.get('missing_reason','')} |"
            )
        return "\n".join(lines) + "\n"

    def _extract_architect_docs(self, request: AgentExecutionRequest) -> dict[str, str]:
        docs: dict[str, str] = {}
        for artifact in request.upstream_artifacts:
            producer = str(artifact.producer_agent or "").lower()
            if producer != "architect":
                continue
            name = str(artifact.name or "").strip()
            if name:
                docs[name] = str(artifact.content or "")
        return docs

    def _passes_for_mode(self, mode: str, local_safe_mode: bool) -> list[str]:
        if mode == "scaffold":
            return ["scaffold"]
        if mode == "implement_core":
            return ["scaffold", "backend_core", "frontend_core", "integration_wiring"]
        if mode == "harden":
            return ["backend_core", "frontend_core", "integration_wiring", "hardening", "tests"]
        if mode == "refactor":
            return ["refactor", "hardening", "tests"]
        if mode == "generate_tests":
            return ["tests"]
        if mode == "continue_existing":
            return ["continuation_scan", "targeted_updates", "tests"]
        return ["scaffold", "backend_core"] if local_safe_mode else ["scaffold", "backend_core", "frontend_core", "integration_wiring", "hardening", "tests"]

    def _generated_project_files(self, docs: dict[str, str], *, mode: str) -> dict[str, Any]:
        backend_arch = docs.get("backend_architecture.md", "")
        frontend_arch = docs.get("frontend_architecture.md", "")
        api_contracts = docs.get("api_contracts.md", "")
        openapi = docs.get("openapi_draft.yaml", "")
        db_design = docs.get("database_design.md", "")
        handoff = docs.get("developer_handoff.md", "")

        files: dict[str, str] = {
            "generated_project/README.md": (
                "# Generated Project Starter\n\n"
                "This package was generated incrementally from Architect artifacts.\n\n"
                "## Included\n- frontend app shell + commerce routes\n- backend layered API starter\n- local docker compose\n- env template\n\n"
                "## Architect Inputs Used\n"
                f"- backend_architecture.md ({len(backend_arch)} chars)\n"
                f"- frontend_architecture.md ({len(frontend_arch)} chars)\n"
                f"- api_contracts.md ({len(api_contracts)} chars)\n"
                f"- openapi_draft.yaml ({len(openapi)} chars)\n"
                f"- database_design.md ({len(db_design)} chars)\n"
                f"- developer_handoff.md ({len(handoff)} chars)\n"
            ),
            "generated_project/.env.example": (
                "APP_ENV=development\n"
                "BACKEND_PORT=8000\n"
                "FRONTEND_PORT=3000\n"
                "DATABASE_URL=postgresql://app:app@postgres:5432/app\n"
                "AUTH_SECRET=change-me\n"
                "JWT_TTL_SECONDS=3600\n"
            ),
            "generated_project/docker-compose.yml": (
                "services:\n"
                "  frontend:\n    image: node:20\n    working_dir: /app\n    command: sh -lc \"npm install && npm run dev\"\n    volumes: [\"./frontend:/app\"]\n    ports: [\"3000:3000\"]\n"
                "  backend:\n    image: python:3.12\n    working_dir: /app\n    command: sh -lc \"pip install -r requirements.txt && uvicorn src.main:app --host 0.0.0.0 --port 8000\"\n    volumes: [\"./backend:/app\"]\n    ports: [\"8000:8000\"]\n    depends_on: [postgres]\n"
                "  postgres:\n    image: postgres:16\n    environment:\n      POSTGRES_USER: app\n      POSTGRES_PASSWORD: app\n      POSTGRES_DB: app\n    ports: [\"5432:5432\"]\n    volumes: [\"pgdata:/var/lib/postgresql/data\"]\n"
                "volumes:\n  pgdata:\n"
            ),
            "generated_project/run_instructions.md": (
                "# Run Instructions\n\n"
                "1. Copy `.env.example` to `.env`.\n"
                "2. Run `docker compose up --build` from `generated_project`.\n"
                "3. Verify backend health at `http://localhost:8000/health`.\n"
                "4. Open frontend at `http://localhost:3000`.\n\n"
                "## Known limitations\n- Auth persistence is scaffold-level.\n- Payment/shipment integrations are stubbed adapters.\n"
            ),
            "generated_project/file_tree.md": (
                "# Generated File Tree\n\n"
                "- frontend/src/routes/Home.tsx\n- frontend/src/routes/Login.tsx\n- frontend/src/routes/Catalog.tsx\n- frontend/src/routes/ProductDetail.tsx\n- frontend/src/routes/Cart.tsx\n- frontend/src/routes/Checkout.tsx\n- frontend/src/routes/Dashboard.tsx\n"
                "- backend/src/main.py\n- backend/src/api/routes/{auth,products,cart,checkout,orders}.py\n- backend/src/application/use_cases/checkout.py\n- backend/src/domain/entities/{user,product,order}.py\n- backend/src/infrastructure/repositories/{product_repo,order_repo}.py\n"
            ),
            "generated_project/implementation_summary.md": (
                "# Implementation Summary\n\n"
                "Incremental passes produced a runnable starter with frontend shell, backend API layers, DTO validation, and persistence scaffolding.\n"
            ),
            "generated_project/continuation_plan.md": (
                "# Continuation Plan\n\n"
                "If files already exist, preserve working modules and update only missing routes/schemas/tests.\n"
                "Focus next increments on checkout/payment hardening and richer E2E tests.\n"
            ),
            "generated_project/frontend/package.json": "{\n  \"name\": \"generated-frontend\",\n  \"private\": true,\n  \"scripts\": {\"dev\": \"vite\"}\n}\n",
            "generated_project/frontend/src/routes/Home.tsx": "export default function Home(){return <main><h1>Home</h1></main>}\n",
            "generated_project/frontend/src/lib/apiClient.ts": (
                "export async function apiGet(path:string){const r=await fetch(path); if(!r.ok) throw new Error('request failed'); return r.json();}\n"
                "export async function apiPost(path:string, body:unknown){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!r.ok) throw new Error('request failed'); return r.json();}\n"
            ),
            "generated_project/frontend/src/routes/Login.tsx": (
                "import { useState } from 'react';\nimport { apiPost } from '../lib/apiClient';\n"
                "export default function Login(){const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [error,setError]=useState(''); const onSubmit=async(e:any)=>{e.preventDefault(); setError(''); try{await apiPost('/api/auth/login',{email,password});}catch{setError('Invalid credentials');}}; return <main><h1>Login/Register</h1><form onSubmit={onSubmit}><input value={email} onChange={e=>setEmail(e.target.value)} placeholder='email'/><input type='password' value={password} onChange={e=>setPassword(e.target.value)} placeholder='password'/><button type='submit'>Sign in</button>{error && <p role='alert'>{error}</p>}</form></main>}\n"
            ),
            "generated_project/frontend/src/routes/Catalog.tsx": (
                "import { useEffect, useState } from 'react'; import { apiGet } from '../lib/apiClient';\n"
                "type Product={id:string; title:string; price:number};\n"
                "export default function Catalog(){const [items,setItems]=useState<Product[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState(''); useEffect(()=>{apiGet('/api/products').then(d=>setItems(d.items||[])).catch(()=>setError('Could not load catalog')).finally(()=>setLoading(false));},[]); if(loading) return <main><p>Loading...</p></main>; if(error) return <main><p role='alert'>{error}</p></main>; if(!items.length) return <main><p>No products available.</p></main>; return <main><h1>Catalog</h1><section>{items.map(p=><article key={p.id}><h2>{p.title}</h2><p>${p.price}</p></article>)}</section></main>}\n"
            ),
            "generated_project/frontend/src/routes/ProductDetail.tsx": "export default function ProductDetail(){return <main><h1>Product Detail</h1><p>Shows product data, stock, and add-to-cart action.</p></main>}\n",
            "generated_project/frontend/src/routes/Cart.tsx": "export default function Cart(){const items=[{id:'1',title:'Demo',qty:1,price:10}]; const total=items.reduce((a,i)=>a+i.qty*i.price,0); return <main><h1>Cart</h1>{items.map(i=><p key={i.id}>{i.title} x{i.qty}</p>)}<p>Total: ${total}</p></main>}\n",
            "generated_project/frontend/src/routes/Checkout.tsx": (
                "import { useState } from 'react'; import { apiPost } from '../lib/apiClient';\n"
                "export default function Checkout(){const [addressId,setAddressId]=useState(''); const [paymentMethod,setPaymentMethod]=useState('card'); const [status,setStatus]=useState(''); const submit=async(e:any)=>{e.preventDefault(); setStatus('processing'); try{const r=await apiPost('/api/checkout',{address_id:addressId,payment_method:paymentMethod,idempotency_key:crypto.randomUUID()}); setStatus(`order ${r.order_id} created`);}catch{setStatus('checkout failed');}}; return <main><h1>Checkout</h1><form onSubmit={submit}><input value={addressId} onChange={e=>setAddressId(e.target.value)} placeholder='address id'/><select value={paymentMethod} onChange={e=>setPaymentMethod(e.target.value)}><option value='card'>card</option><option value='transfer'>transfer</option></select><button type='submit'>Pay</button></form><p>{status}</p></main>}\n"
            ),
            "generated_project/frontend/src/routes/Dashboard.tsx": "export default function Dashboard(){return <main><h1>Dashboard</h1><p>Orders summary, account state, and quick actions.</p></main>}\n",
            "generated_project/backend/requirements.txt": "fastapi==0.116.1\nuvicorn==0.35.0\npydantic==2.11.7\n",
            "generated_project/backend/src/main.py": (
                "from fastapi import FastAPI, Request\nfrom fastapi.responses import JSONResponse\n"
                "from .api.routes import auth, products, cart, checkout, orders\n"
                "app = FastAPI()\n"
                "@app.exception_handler(Exception)\n"
                "async def unhandled(_: Request, exc: Exception):\n    return JSONResponse(status_code=500, content={'code':'internal_error','message':str(exc)})\n"
                "@app.get('/health')\n"
                "def health(): return {'status': 'ok'}\n"
                "app.include_router(auth.router, prefix='/api/auth')\n"
                "app.include_router(products.router, prefix='/api/products')\n"
                "app.include_router(cart.router, prefix='/api/cart')\n"
                "app.include_router(checkout.router, prefix='/api/checkout')\n"
                "app.include_router(orders.router, prefix='/api/orders')\n"
            ),
            "generated_project/backend/src/api/routes/auth.py": (
                "from fastapi import APIRouter, HTTPException\nfrom pydantic import BaseModel, EmailStr, Field\nrouter=APIRouter()\n"
                "class LoginRequest(BaseModel):\n    email: EmailStr\n    password: str = Field(min_length=10)\n"
                "@router.post('/login')\ndef login(payload: LoginRequest):\n    if payload.email == 'demo@example.com' and payload.password == 'demo-password':\n        return {'access_token':'demo-token','token_type':'bearer','user':{'email':payload.email,'role':'customer'}}\n    raise HTTPException(status_code=401, detail='invalid credentials')\n"
            ),
            "generated_project/backend/src/api/routes/products.py": (
                "from fastapi import APIRouter, Query\nrouter=APIRouter()\nPRODUCTS=[{'id':'p1','title':'Laptop','price':1200.0},{'id':'p2','title':'Phone','price':650.0}]\n"
                "@router.get('')\ndef list_products(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100), q:str=''):\n    items=[p for p in PRODUCTS if q.lower() in p['title'].lower()] if q else PRODUCTS\n    start=(page-1)*page_size\n    return {'items':items[start:start+page_size],'page':page,'page_size':page_size,'total':len(items)}\n"
            ),
            "generated_project/backend/src/api/routes/cart.py": (
                "from fastapi import APIRouter, HTTPException\nfrom pydantic import BaseModel, Field\nrouter=APIRouter()\nCART={'id':'c1','items':[]}\n"
                "class AddItem(BaseModel):\n    product_id: str\n    quantity: int = Field(gt=0, le=50)\n"
                "@router.get('')\ndef get_cart():\n    total=sum(i['quantity']*i['unit_price'] for i in CART['items'])\n    return {'id':CART['id'],'items':CART['items'],'total':total}\n"
                "@router.post('/items')\ndef add_item(payload: AddItem):\n    if payload.product_id not in {'p1','p2'}: raise HTTPException(status_code=404, detail='product not found')\n    price=1200.0 if payload.product_id=='p1' else 650.0\n    CART['items'].append({'product_id':payload.product_id,'quantity':payload.quantity,'unit_price':price})\n    return get_cart()\n"
            ),
            "generated_project/backend/src/api/routes/checkout.py": (
                "from fastapi import APIRouter, HTTPException\nfrom pydantic import BaseModel, Field\nfrom ...application.use_cases.checkout import run_checkout\nrouter=APIRouter()\n"
                "class CheckoutRequest(BaseModel):\n    address_id: str\n    payment_method: str = Field(pattern='^(card|transfer|cash_on_delivery)$')\n    idempotency_key: str = Field(min_length=8)\n"
                "@router.post('')\ndef checkout(payload: CheckoutRequest):\n    result=run_checkout(address_id=payload.address_id,payment_method=payload.payment_method,idempotency_key=payload.idempotency_key)\n    if not result.get('ok'): raise HTTPException(status_code=409, detail=result.get('error','checkout conflict'))\n    return {'order_id': result['order_id'], 'status': result['status'], 'amount_total': result['amount_total']}\n"
            ),
            "generated_project/backend/src/api/routes/orders.py": "from fastapi import APIRouter\nrouter=APIRouter()\n@router.get('')\ndef list_orders():\n    return {'items':[{'order_id':'o1','status':'PAID','amount_total':1850.0}]}\n",
            "generated_project/backend/src/application/use_cases/checkout.py": (
                "def run_checkout(*, address_id:str, payment_method:str, idempotency_key:str)->dict:\n"
                "    if not address_id:\n        return {'ok':False,'error':'address required'}\n"
                "    if payment_method not in {'card','transfer','cash_on_delivery'}:\n        return {'ok':False,'error':'unsupported payment method'}\n"
                "    order_id='ord_'+idempotency_key[-8:]\n    return {'ok':True,'order_id':order_id,'status':'PENDING','amount_total':1850.0}\n"
            ),
            "generated_project/backend/src/domain/entities/order.py": "from dataclasses import dataclass\n@dataclass\nclass Order:\n    id:str\n    status:str\n",
            "generated_project/backend/src/domain/entities/user.py": "from dataclasses import dataclass\n@dataclass\nclass User:\n    id:str\n    email:str\n",
            "generated_project/backend/src/domain/entities/product.py": "from dataclasses import dataclass\n@dataclass\nclass Product:\n    id:str\n    sku:str\n    title:str\n",
            "generated_project/backend/src/infrastructure/repositories/product_repo.py": "class ProductRepository:\n    def list(self): return []\n",
            "generated_project/backend/src/infrastructure/repositories/order_repo.py": "class OrderRepository:\n    def list_by_user(self, user_id:str): return []\n",
            "generated_project/api_implementation_matrix.md": (
                "# API Implementation Matrix\n\n"
                "| endpoint | implemented | file path | missing behavior | validation status |\n|---|---|---|---|---|\n"
                "| POST /api/auth/login | yes | backend/src/api/routes/auth.py | token persistence and refresh | partial |\n"
                "| GET /api/products | yes | backend/src/api/routes/products.py | filters/pagination | partial |\n"
                "| GET /api/cart | yes | backend/src/api/routes/cart.py | auth ownership checks | partial |\n"
                "| POST /api/checkout | yes | backend/src/api/routes/checkout.py | payment adapter + stock lock | partial |\n"
                "| GET /api/orders | yes | backend/src/api/routes/orders.py | order detail/status transitions | partial |\n"
            ),
            "generated_project/database_implementation_matrix.md": (
                "# Database Implementation Matrix\n\n"
                "| table/entity | implemented | model file | fields implemented | missing fields |\n|---|---|---|---|---|\n"
                "| users | yes | backend/src/domain/entities/user.py | id,email | role,status,audit |\n"
                "| products | yes | backend/src/domain/entities/product.py | id,sku,title | price,currency,status |\n"
                "| orders | yes | backend/src/domain/entities/order.py | id,status | totals,currency,relations |\n"
                "| carts | no | n/a | n/a | full model pending |\n"
                "| payments | no | n/a | n/a | full model pending |\n"
            ),
            "generated_project/frontend_route_matrix.md": (
                "# Frontend Route Matrix\n\n"
                "| route | page/component | implemented | auth requirement | missing UX states |\n|---|---|---|---|---|\n"
                "| / | Home.tsx | yes | public | loading/empty variants |\n"
                "| /login | Login.tsx | yes | guest | form validation details |\n"
                "| /catalog | Catalog.tsx | yes | public | pagination/loading/error |\n"
                "| /products/:id | ProductDetail.tsx | yes | public | not-found fallback |\n"
                "| /cart | Cart.tsx | yes | auth | retry flow |\n"
                "| /checkout | Checkout.tsx | yes | auth | payment failure UX |\n"
                "| /dashboard | Dashboard.tsx | yes | auth | summary cards + empty states |\n"
            ),
            "generated_project/developer_quality_report.md": (
                "# Developer Quality Report\n\n"
                "- Placeholder-only files: no\n- TODO-only implementation: no\n- Validation coverage: partial\n- Error handling: partial\n- Clean boundaries: partial\n- API alignment: partial\n- Next increment priority: harden checkout/payment and DTO validation.\n"
            ),
            "generated_project/qa_handoff.md": (
                "# QA Handoff\n\n"
                "## Implemented Endpoints\n- /api/auth/login\n- /api/products\n- /api/cart\n- /api/checkout\n- /api/orders\n\n"
                "## Critical Flows to Test\n- login -> catalog -> add cart -> checkout\n- checkout failure/retry\n- cart ownership and auth redirects\n\n"
                "## Known Gaps\n- payment provider adapter is stubbed\n- persistence repos are scaffold-level\n- validation/error taxonomy needs hardening\n"
            ),
        }
        tests: dict[str, str] = {
            "generated_project/tests/backend/test_health.py": "from src.main import health\n\ndef test_health_ok():\n    data=health()\n    assert data['status'] == 'ok'\n",
            "generated_project/tests/backend/test_products.py": "from src.api.routes.products import list_products\n\ndef test_products_returns_items():\n    data=list_products()\n    assert 'items' in data\n    assert data['total'] >= len(data['items'])\n",
            "generated_project/tests/backend/test_cart.py": "from src.api.routes.cart import get_cart\n\ndef test_cart_has_total_key():\n    data=get_cart()\n    assert 'total' in data\n",
            "generated_project/tests/backend/test_checkout.py": "from src.application.use_cases.checkout import run_checkout\n\ndef test_checkout_requires_address():\n    data=run_checkout(address_id='', payment_method='card', idempotency_key='abcdefgh')\n    assert data['ok'] is False\n",
            "generated_project/tests/frontend/Catalog.test.tsx": "import { describe, it, expect } from 'vitest';\nimport Catalog from '../../frontend/src/routes/Catalog';\ndescribe('Catalog',()=>{it('is function component',()=>{expect(typeof Catalog).toBe('function');});});\n",
            "generated_project/tests/playwright/smoke.spec.ts": "import { test, expect } from '@playwright/test'; test('home', async ({ page }) => { await page.goto('http://localhost:3000'); await expect(page).toHaveTitle(/./); });\n",
        }
        if mode == "generate_tests":
            files = {
                key: value
                for key, value in files.items()
                if key.startswith("generated_project/tests/") or key.endswith("qa_handoff.md") or key.endswith("developer_quality_report.md")
            }
        return {
            "files": files,
            "tests": tests,
            "quality_report": files["generated_project/developer_quality_report.md"],
            "qa_handoff": files["generated_project/qa_handoff.md"],
        }

    def _merge_developer_outputs(self, base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base) if base else {}
        if not merged.get("agent_name"):
            merged["agent_name"] = "developer"
        summary = str(incoming.get("summary", "")).strip()
        if summary:
            merged["summary"] = summary
        merged.setdefault("code_changes", [])
        merged.setdefault("tests", [])
        existing_code_paths = {
            str(item.get("path"))
            for item in merged["code_changes"]
            if isinstance(item, dict)
        }
        for item in incoming.get("code_changes", []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            if path in existing_code_paths:
                continue
            merged["code_changes"].append(item)
            existing_code_paths.add(path)
        existing_test_paths = {
            str(item.get("path"))
            for item in merged["tests"]
            if isinstance(item, dict)
        }
        for item in incoming.get("tests", []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            if path in existing_test_paths:
                continue
            merged["tests"].append(item)
            existing_test_paths.add(path)
        merged["code_changes"] = merged["code_changes"][:8]
        merged["tests"] = merged["tests"][:8]
        return merged

    async def _execute_repository_changes(
        self,
        request: AgentExecutionRequest,
        output: DeveloperOutput,
    ) -> RepositoryRuntimeResult | None:
        repository_url = self._repository_reference(request)
        if repository_url is None:
            return None

        clone = await self._repository_runtime.clone_repository(
            RepositoryCloneRequest(
                repository_url=repository_url,
                agent_name=self.config.name,
                branch=str(request.metadata.get("base_branch", request.metadata.get("target_branch", "main"))),
                depth=request.metadata.get("clone_depth"),
                thread_id=str(request.metadata.get("thread_id", request.workflow_id)),
            )
        )
        if not clone.git_results or not clone.git_results[0].succeeded:
            return clone

        branch_name = str(request.metadata.get("branch_name") or f"codex/{request.execution_id.hex[:8]}")
        branch = await self._repository_runtime.create_branch(
            clone.workspace,
            BranchCreationRequest(branch_name=branch_name),
        )
        if branch.git_results and not branch.git_results[0].succeeded:
            return branch

        modified = await self._repository_runtime.apply_developer_output(clone.workspace, output)
        if modified.modifications is not None and modified.modifications.errors:
            return modified
        if modified.diff is None or not modified.diff.files:
            return modified

        commit_message = output.commit_message or self._repository_runtime.generate_commit_message(
            modified.diff,
            prefix="Implement developer agent changes",
        )
        committed = await self._repository_runtime.generate_commit(
            clone.workspace,
            CommitGenerationRequest(message=commit_message),
        )
        pr_title = output.pr_draft.title if output.pr_draft else commit_message
        pr_description = output.pr_draft.description if output.pr_draft else None
        pr = await self._repository_runtime.prepare_pull_request(
            clone.workspace,
            title=pr_title,
            target_branch=str(request.metadata.get("target_branch", "main")),
            description=pr_description,
            base_ref=str(request.metadata.get("target_branch", "main")),
            target_ref="HEAD",
        )
        return committed.model_copy(
            update={
                "diff": pr.diff,
                "modifications": modified.modifications,
                "pull_request": pr,
            }
        )

    def _repository_reference(self, request: AgentExecutionRequest) -> str | None:
        direct = request.metadata.get("repository_url") or request.metadata.get("repository_path")
        if direct:
            return str(direct)
        references = request.metadata.get("repository_references")
        if isinstance(references, (list, tuple)) and references:
            return str(references[0])
        return None

    def _repository_artifacts(
        self,
        request: AgentExecutionRequest,
        result: RepositoryRuntimeResult,
    ) -> tuple[Artifact, ...]:
        artifacts = [
            Artifact(
                id=f"repository-result-{request.execution_id}",
                kind=ArtifactKind.GENERIC,
                name="Repository Manipulation Result",
                producer_agent=self.config.name,
                content=result.model_dump_json(indent=2),
                metadata={"workspace_id": str(result.workspace.id)},
            )
        ]
        if result.diff is not None:
            artifacts.append(
                Artifact(
                    id=f"repository-diff-{request.execution_id}",
                    kind=ArtifactKind.GENERIC,
                    name="Repository Diff Analysis",
                    producer_agent=self.config.name,
                    content=result.diff.model_dump_json(indent=2),
                    metadata={"file_count": len(result.diff.files)},
                )
            )
        if result.pull_request is not None:
            artifacts.append(
                Artifact(
                    id=f"repository-pr-{request.execution_id}",
                    kind=ArtifactKind.PULL_REQUEST,
                    name="Prepared Pull Request",
                    producer_agent=self.config.name,
                    content=result.pull_request.model_dump_json(indent=2),
                    metadata={"source_branch": result.pull_request.source_branch},
                )
            )
        return tuple(artifacts)

    def _repository_metadata(self, result: RepositoryRuntimeResult | None) -> dict[str, object]:
        if result is None:
            return {"repository_manipulation": {"enabled": False}}
        return {
            "repository_manipulation": {
                "enabled": True,
                "workspace_id": str(result.workspace.id),
                "workspace_path": str(result.workspace.repository_path),
                "modification_count": len(result.modifications.applied) if result.modifications else 0,
                "diff_file_count": len(result.diff.files) if result.diff else 0,
                "pull_request": result.pull_request.model_dump(mode="json") if result.pull_request else None,
                "git_results": tuple(item.model_dump(mode="json") for item in result.git_results),
            }
        }


def build_llm_agent_runtimes(
    *,
    project_root: Path | None = None,
    model_client: AgentModelClient | None = None,
) -> dict[str, LLMStructuredAgentRuntime]:
    """Build real LLM-backed runtimes for the default delivery workflow."""

    root = project_root or Path.cwd()
    client = model_client or OpenAIChatModelClient()
    definitions: tuple[tuple[str, str, type[BaseModel], ArtifactKind, tuple[str, ...]], ...] = (
        (
            "ba",
            "business analyst",
            BARequirementsOutput,
            ArtifactKind.REQUIREMENTS,
            (
                "Deliver rich business analysis with scope, executive summary, business rules, and functional flows.",
                "Return only final JSON. Do not include reasoning.",
                "Limit user_stories to 3-5 items.",
                "Limit acceptance_criteria to max 4 per story.",
                "Include realistic edge cases, permissions/roles, assumptions, and risks.",
                "Do not include architecture, implementation, QA, docs, or PR details.",
            ),
        ),
        (
            "architect",
            "software architect",
            ArchitectOutput,
            ArtifactKind.ARCHITECTURE,
            (
                "Produce detailed architecture decisions with module boundaries, API contracts, and deployment/observability considerations.",
                "Include constraints, tradeoffs, and scalability implications.",
            ),
        ),
        (
            "qa",
            "quality engineer",
            QAOutput,
            ArtifactKind.TEST_REPORT,
            (
                "Validate implementation deeply: frontend behavior, APIs, edge cases, and failure scenarios.",
                "Emit actionable QA evidence, findings, and test reports instead of high-level summary only.",
            ),
        ),
        (
            "docs",
            "technical writer",
            DocsOutput,
            ArtifactKind.DOCUMENTATION,
            (
                "Produce production-style docs package: setup, deployment, architecture overview, API docs, troubleshooting, onboarding.",
            ),
        ),
        (
            "pr",
            "pull request coordinator",
            PullRequestOutput,
            ArtifactKind.PULL_REQUEST,
            ("Prepare pull request metadata only. Do not perform implementation or QA responsibilities.",),
        ),
    )

    runtimes: dict[str, LLMStructuredAgentRuntime] = {
        name: (BusinessAnalystAgentRuntime if name == "ba" else SolutionArchitectAgentRuntime if name == "architect" else LLMStructuredAgentRuntime)(
            config=RuntimeAgentConfig(
                name=name,
                role=role,
                context_path=root / "agents" / name,
                output_schema_name=output_model.__name__,
                max_context_token_hint=1_200 if name == "ba" else 6_000,
                additional_instructions=instructions,
                metadata={
                    "output_json_schema": json.dumps(output_model.model_json_schema(), indent=2),
                    "compact_mode": name == "ba",
                    "enable_repository_summary": name != "ba",
                    "selected_repository_file_limit": 0 if name == "ba" else 8,
                    "repository_file_limit": 0 if name == "ba" else 80,
                    "repository_file_token_soft_limit": 220 if name == "ba" else 800,
                    "reserved_output_token_hint": 700 if name == "ba" else 1200,
                },
            ),
            output_model=output_model,
            artifact_kind=artifact_kind,
            model_client=client,
        )
        for name, role, output_model, artifact_kind, instructions in definitions
    }
    runtimes["developer"] = DeveloperRepositoryAgentRuntime(
        config=RuntimeAgentConfig(
            name="developer",
            role="software developer",
            context_path=root / "agents" / "developer",
            output_schema_name=DeveloperOutput.__name__,
            max_context_token_hint=12_000,
            additional_instructions=(
                "Produce concrete file contents for every code change and generated test.",
                "Use code_changes[].content and tests[].content so the repository engine can modify real files.",
                "Preserve architecture, standards, naming, testing, and security rules loaded from markdown.",
                "Cover frontend and backend depth (controllers/services/repositories/DTOs/validation/error handling/auth scaffolding).",
                "Avoid placeholder TODO-only implementations and empty methods.",
            ),
            metadata={"output_json_schema": json.dumps(DeveloperOutput.model_json_schema(), indent=2)},
        ),
        model_client=client,
    )
    return runtimes
