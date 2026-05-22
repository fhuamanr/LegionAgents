"""LLM-backed executable agents for the delivery workflow."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from pydantic import BaseModel

from core.agents.model_clients import OpenAIChatModelClient
from core.agents.runtime import AgentModelClient
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.execution import AgentExecutionRequest
from core.contracts.outputs import (
    ArchitectOutput,
    BARequirementsOutput,
    DeveloperOutput,
    DocsOutput,
    OutputContractKind,
    PullRequestOutput,
    QAOutput,
)
from core.runtime.agent import BaseAgent
from core.runtime.context import GovernanceRuntimeContextAssembler
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
            "developer",
            "software developer",
            DeveloperOutput,
            ArtifactKind.SOURCE_CODE,
            ("Produce code-generation plans, test proposals, refactoring suggestions, commit text, and PR draft only.",),
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

    return {
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
