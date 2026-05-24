"""Base agent runtime architecture."""

import logging
import time
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
            result = await self._retry_engine.run(
                lambda: self._execute_once(request),
                on_decision=self._on_retry_decision,
            )
        except Exception as exc:
            self._logger.exception("agent_execution_failed", extra={"agent_name": self.config.name})
            error_text = str(exc)
            if "json_parse_error:" in error_text:
                error_type = "json_parse_error"
            elif "schema_contract_error:" in error_text:
                error_type = "schema_contract_error"
            elif "Output is not valid JSON" in error_text:
                error_type = "json_parse_error"
            else:
                error_type = "runtime_error"
            return self._failure(
                request=request,
                errors=(error_text,),
                metadata={"error_type": error_type, "raw_output_preview": error_text[:1200], "retry_allowed": False},
            )

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
        prompt_messages, prompt_budget_observability = self._enforce_local_safe_prompt_budget(request, prompt_messages)
        runtime_context = runtime_context.model_copy(
            update={"prompt_messages": prompt_messages}
        )

        started = time.perf_counter()
        raw_output = await self.invoke(runtime_context)
        duration_seconds = max(0.0, time.perf_counter() - started)
        await self._enforce_governance_output(runtime_context, raw_output)
        parse_strategy = "ba_sections" if (self.config.name == "ba" and bool(request.metadata.get("local_lm_studio_safe_mode", False))) else None
        structured_output = await self._output_validator.validate(raw_output, strategy=parse_strategy)
        validation_metadata = dict(getattr(self._output_validator, "last_validation_metadata", {}))
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
                "prompt_budget": prompt_budget_observability,
                "validation": validation_metadata,
                "observability": {
                    "prompt_token_estimate": sum(max(1, len(message.content) // 4) for message in prompt_messages),
                    "output_token_estimate": max(1, len(raw_output) // 4),
                    "generation_duration_seconds": round(duration_seconds, 3),
                    "model_tokens_per_second_estimate": round((max(1, len(raw_output) // 4) / duration_seconds), 2) if duration_seconds > 0 else None,
                    "raw_output_size": len(raw_output),
                    "json_extracted": validation_metadata.get("json_extracted", False),
                    "sanitization_applied": validation_metadata.get("sanitization_applied", False),
                    "fields_removed": validation_metadata.get("fields_removed", []),
                    "validation_result": validation_metadata.get("validation_result", "unknown"),
                    "parse_strategy": parse_strategy or "json",
                },
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
        metadata: dict[str, object] | None = None,
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self.config.name,
            status=AgentStatus.FAILED,
            errors=errors,
            metadata=metadata or {},
        )

    def _on_retry_decision(self, event) -> None:
        self._logger.warning(
            event.event_type,
            extra={
                "agent_name": self.config.name,
                "attempt": event.attempt,
                "max_attempts": event.max_attempts,
                "classification": event.classification,
                "retry_allowed": event.retry_allowed,
                "compression_allowed": event.compression_allowed,
                "error_type": event.error_type,
                "suggested_action": event.suggested_action,
            },
        )

    def _enforce_local_safe_prompt_budget(
        self,
        request: AgentExecutionRequest,
        prompt_messages: tuple,
    ) -> tuple[tuple, dict[str, object]]:
        safe_mode = bool(request.metadata.get("local_lm_studio_safe_mode", False))
        before = sum(max(1, len(message.content) // 4) for message in prompt_messages)
        obs: dict[str, object] = {
            "prompt_tokens_before": before,
            "prompt_tokens_after": before,
            "sections_removed": 0,
            "final_prompt_tokens": before,
        }
        budgets = {
            "ba": 900,
            "architect": 1200,
            "developer": 1400,
            "qa": 1000,
            "docs": 900,
            "pr": 700,
        }
        output_budgets = {
            "ba": 450,
            "architect": 600,
            "developer": 700,
            "qa": 500,
            "docs": 500,
            "pr": 350,
        }
        max_tokens = int(budgets.get(self.config.name, 1200))
        obs["budget"] = max_tokens
        obs["output_budget"] = int(output_budgets.get(self.config.name, 600))
        if not safe_mode:
            return prompt_messages, obs
        if before <= max_tokens:
            return prompt_messages, obs

        compact_system = prompt_messages[0].content
        compact_user = f"# Task\n\n{request.task.strip()}\n\n# Upstream Summary\n"
        compact_user += "\n".join(
            f"- {artifact.kind.value}: {artifact.name} ({artifact.producer_agent})"
            for artifact in request.upstream_artifacts[:3]
        )
        if self.config.name == "ba":
            compact_system = (
                "You are the BA agent. Return only final answer. Do not include reasoning. "
                "Do not output JSON."
            )
            compact_user += (
                "\n\nOUTPUT FORMAT (STRICT):\n"
                "NORMALIZED_REQUIREMENT:\n"
                "...\n\n"
                "USER_STORIES:\n"
                "1. As a..., I want..., so that...\n"
                "   AC:\n"
                "   - ...\n\n"
                "ASSUMPTIONS:\n"
                "- ...\n\n"
                "RISKS:\n"
                "- ...\n\n"
                "DEPENDENCIES:\n"
                "- ...\n"
            )
        elif self.config.name == "architect":
            compact_user += (
                "\n\nOutput only compact architecture summary: "
                "technical approach (max 5 bullets), affected areas (max 5), constraints (max 3)."
            )

        compact = (
            prompt_messages[0].model_copy(update={"content": compact_system}),
            prompt_messages[1].model_copy(update={"content": compact_user}),
        )
        after = sum(max(1, len(message.content) // 4) for message in compact)
        obs.update(
            {
                "prompt_tokens_after": after,
                "sections_removed": 1,
                "final_prompt_tokens": after,
                "compression_applied": True,
            }
        )
        if after > max_tokens:
            raise ValueError(
                f"{self.config.name} prompt too large for local safe mode after reduction. "
                f"prompt_tokens_before={before} prompt_tokens_after={after} max_prompt_tokens={max_tokens}"
            )
        return compact, obs
