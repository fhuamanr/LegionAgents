"""Base agent runtime architecture."""

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.governance import GovernancePolicy, GovernanceRule, PolicyValidator
from core.runtime.context import ContextAssembler, MarkdownRuleContextAssembler
from core.runtime.models import RuntimeAgentConfig, RuntimeExecutionContext
from core.runtime.prompts import PromptBuilder, RuntimePromptBuilder
from core.runtime.retry import RetryEngine
from core.runtime.tools import ToolRegistry
from core.runtime.validation import OutputValidator

TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseAgent(ABC, Generic[TOutput]):
    """Reusable async-first base class for isolated agents."""

    def __init__(
        self,
        config: RuntimeAgentConfig,
        output_validator: OutputValidator[TOutput],
        context_assembler: ContextAssembler | None = None,
        prompt_builder: PromptBuilder | None = None,
        retry_engine: RetryEngine | None = None,
        tool_registry: ToolRegistry | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self._output_validator = output_validator
        self._context_assembler = context_assembler or MarkdownRuleContextAssembler()
        self._prompt_builder = prompt_builder or RuntimePromptBuilder()
        self._retry_engine = retry_engine or RetryEngine()
        self._tool_registry = tool_registry or ToolRegistry()
        self._logger = logger or logging.getLogger(f"{__name__}.{config.name}")

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        """Execute this agent with isolated context, retries, and validation."""

        if request.agent_name != self.config.name:
            return self._failure(
                request=request,
                errors=(f"Agent {self.config.name} cannot execute request for {request.agent_name}.",),
            )

        self._logger.info("agent_execution_started", extra={"agent_name": self.config.name})
        try:
            result = await self._retry_engine.run(lambda: self._execute_once(request))
        except Exception as exc:
            self._logger.exception("agent_execution_failed", extra={"agent_name": self.config.name})
            return self._failure(request=request, errors=(str(exc),))

        self._logger.info("agent_execution_completed", extra={"agent_name": self.config.name})
        return result

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
        runtime_context = runtime_context.model_copy(
            update={"prompt_messages": prompt_messages}
        )

        raw_output = await self.invoke(runtime_context)
        await self._enforce_governance_output(runtime_context, raw_output)
        structured_output = await self._output_validator.validate(raw_output)
        await self._enforce_governance_output(runtime_context, raw_output, structured_output)
        artifacts = await self.build_artifacts(request, structured_output)
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
                **self.result_metadata(structured_output),
            },
        )

    async def _enforce_governance_output(
        self,
        context: RuntimeExecutionContext,
        raw_output: str,
        structured_output: BaseModel | None = None,
    ) -> None:
        policy = self._governance_policy_from_context(context)
        if policy is None:
            return
        validator = PolicyValidator()
        policy_result = validator.validate_policy(policy)
        output_result = (
            validator.validate_runtime_text(policy, raw_output)
            if structured_output is None
            else validator.validate_generated_output(
                policy,
                agent_name=self.config.name,
                raw_output=raw_output,
                structured_output=structured_output,
            )
        )
        errors = policy_result.errors + output_result.errors
        if errors:
            raise ValueError("Governance runtime rejection: " + "; ".join(errors))

    def _governance_policy_from_context(self, context: RuntimeExecutionContext) -> GovernancePolicy | None:
        rules = context.agent_context.metadata.get("governance_rules")
        if not rules:
            return None
        return GovernancePolicy(
            name=str(context.agent_context.metadata.get("governance_policy_name", "Runtime Governance Policy")),
            scope=self.config.name,
            rules=tuple(GovernanceRule.model_validate(rule) for rule in rules),
            metadata={"source": "runtime_context"},
        )

    @abstractmethod
    async def invoke(self, context: RuntimeExecutionContext) -> str:
        """Invoke the underlying model or agent implementation."""

    def summarize(self, output: TOutput) -> str:
        """Return a concise summary for execution results."""

        summary = getattr(output, "summary", None)
        return str(summary) if summary else self.config.name

    def result_metadata(self, output: TOutput) -> dict[str, object]:
        """Return agent-specific metadata for routing and telemetry."""

        return {}

    async def build_artifacts(
        self,
        request: AgentExecutionRequest,
        output: TOutput,
    ) -> tuple[Artifact, ...]:
        """Build default structured-output artifact."""

        artifact = Artifact(
            id=f"{self.config.name}-{request.execution_id}",
            kind=ArtifactKind.GENERIC,
            name=f"{self.config.name} structured output",
            producer_agent=self.config.name,
            content=output.model_dump_json(indent=2),
        )
        return (artifact,)

    def _failure(
        self,
        request: AgentExecutionRequest,
        errors: tuple[str, ...],
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self.config.name,
            status=AgentStatus.FAILED,
            errors=errors,
        )
