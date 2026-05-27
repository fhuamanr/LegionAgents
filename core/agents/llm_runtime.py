"""LLM-backed executable agents for the delivery workflow."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from pydantic import BaseModel

from core.agents.model_clients import OpenAIChatModelClient
from core.agents.ba_intelligence import build_ba_intelligence_bundle
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

    def result_metadata(self, output: BaseModel) -> dict[str, object]:
        base = super().result_metadata(output)
        if not isinstance(output, BARequirementsOutput):
            return base
        bundle = build_ba_intelligence_bundle(
            task=str(getattr(output, "summary", "")),
            structured_output=output.model_dump(mode="json"),
        )
        base["ba_intelligence"] = bundle
        return base


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
        structured_output, raw_output = await self._run_multipass_development(runtime_context, request)
        await self._enforce_governance_output(runtime_context, raw_output)
        await self._enforce_governance_output(runtime_context, raw_output, structured_output)
        if not isinstance(structured_output, DeveloperOutput):
            raise TypeError("Developer runtime must return DeveloperOutput.")

        repository_result = await self._execute_repository_changes(request, structured_output)
        artifacts = await self.build_artifacts(request, structured_output)
        if repository_result is not None:
            artifacts = artifacts + self._repository_artifacts(request, repository_result)

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
                **self.result_metadata(structured_output),
                **self._repository_metadata(repository_result),
            },
        )

    async def _run_multipass_development(
        self,
        runtime_context: RuntimeExecutionContext,
        request: AgentExecutionRequest,
    ) -> tuple[DeveloperOutput, str]:
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
            merged_payload = self._merge_developer_outputs(merged_payload, phase_structured.model_dump(mode="json"))
        if not merged_payload:
            fallback = await self._output_validator.validate(all_raw_outputs[-1] if all_raw_outputs else "", strategy="developer_sections")
            assert isinstance(fallback, DeveloperOutput)
            return fallback, "\n\n".join(all_raw_outputs)
        merged_structured = DeveloperOutput.model_validate(merged_payload)
        return merged_structured, "\n\n".join(all_raw_outputs)

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
        name: (BusinessAnalystAgentRuntime if name == "ba" else LLMStructuredAgentRuntime)(
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
