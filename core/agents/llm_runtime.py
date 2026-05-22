"""LLM-backed executable agents for the delivery workflow."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from pydantic import BaseModel

from core.agents.model_clients import OpenAIChatModelClient
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

        raw_output = await self.invoke(runtime_context)
        structured_output = await self._output_validator.validate(raw_output)
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
                "structured_output": structured_output.model_dump(mode="json"),
                **self.result_metadata(structured_output),
                **self._repository_metadata(repository_result),
            },
        )

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
            ("Extract and normalize BA stories and acceptance criteria only.",),
        ),
        (
            "architect",
            "software architect",
            ArchitectOutput,
            ArtifactKind.ARCHITECTURE,
            ("Produce architecture decisions and constraints only.",),
        ),
        (
            "qa",
            "quality engineer",
            QAOutput,
            ArtifactKind.TEST_REPORT,
            ("Validate upstream implementation artifacts and emit QA evidence only.",),
        ),
        (
            "docs",
            "technical writer",
            DocsOutput,
            ArtifactKind.DOCUMENTATION,
            ("Produce documentation deliverables only after QA context is available.",),
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
        name: LLMStructuredAgentRuntime(
            config=RuntimeAgentConfig(
                name=name,
                role=role,
                context_path=root / "agents" / name,
                output_schema_name=output_model.__name__,
                max_context_token_hint=12_000,
                additional_instructions=instructions,
                metadata={"output_json_schema": json.dumps(output_model.model_json_schema(), indent=2)},
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
            ),
            metadata={"output_json_schema": json.dumps(DeveloperOutput.model_json_schema(), indent=2)},
        ),
        model_client=client,
    )
    return runtimes
