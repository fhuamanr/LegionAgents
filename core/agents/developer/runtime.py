"""Executable Developer Agent runtime."""

import logging

from pydantic import ValidationError

from core.agents.developer.contracts import DeveloperRuntimeConfig
from core.agents.developer.parser import DeveloperOutputParser, format_validation_error
from core.agents.developer.prompts import DeveloperPromptBuilder
from core.agents.developer.repository import FileSystemRepositoryAnalyzer, RepositoryAnalyzer
from core.agents.developer.telemetry import (
    DeveloperTelemetryHook,
    NoopDeveloperTelemetryHook,
)
from core.agents.runtime import AgentModelClient, AgentRuntime
from core.context import FileSystemAgentContextLoader
from core.contracts.agents import AgentDefinition, AgentStatus
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.context import ContextLoadRequest
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.outputs import OutputContract
from core.runtime.retry import RetryEngine, RetryPolicy


class DeveloperAgentRuntime(AgentRuntime):
    """Executable runtime for the developer agent.

    The runtime performs developer-agent mechanics only: rule loading,
    repository analysis, prompt construction, model invocation, output parsing,
    telemetry, and result packaging.
    """

    def __init__(
        self,
        config: DeveloperRuntimeConfig,
        model_client: AgentModelClient,
        context_loader: FileSystemAgentContextLoader | None = None,
        repository_analyzer: RepositoryAnalyzer | None = None,
        prompt_builder: DeveloperPromptBuilder | None = None,
        output_parser: DeveloperOutputParser | None = None,
        retry_engine: RetryEngine | None = None,
        telemetry_hook: DeveloperTelemetryHook | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._model_client = model_client
        self._context_loader = context_loader or FileSystemAgentContextLoader()
        self._repository_analyzer = repository_analyzer or FileSystemRepositoryAnalyzer()
        self._prompt_builder = prompt_builder or DeveloperPromptBuilder()
        self._output_parser = output_parser or DeveloperOutputParser()
        self._retry_engine = retry_engine or RetryEngine(RetryPolicy(max_attempts=2))
        self._telemetry_hook = telemetry_hook or NoopDeveloperTelemetryHook()
        self._logger = logger or logging.getLogger(f"{__name__}.{config.agent_name}")

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        if request.agent_name != self._config.agent_name:
            return self._failed_result(
                request=request,
                errors=(f"Developer runtime cannot execute request for agent: {request.agent_name}",),
                warnings=tuple(),
            )

        self._logger.info("developer_agent_execution_started", extra={"agent": self._config.agent_name})
        await self._telemetry_hook.emit(
            "developer_agent_execution_started",
            {"agent": self._config.agent_name, "execution_id": str(request.execution_id)},
        )

        context_result = await self._context_loader.load_request(
            ContextLoadRequest(
                agent_name=self._config.agent_name,
                root_path=self._config.context_path,
                max_token_hint=self._config.max_context_token_hint,
            )
        )
        required_rules, rule_warnings = self._load_required_rules()
        repository_analysis = await self._repository_analyzer.analyze(self._config.repository_path)
        messages = await self._prompt_builder.build(
            request=request,
            config=self._config,
            agent_context=context_result.context,
            repository_analysis=repository_analysis,
            required_rules=required_rules,
        )

        try:
            raw_output = await self._retry_engine.run(lambda: self._model_client.complete(messages))
            structured_output = self._output_parser.parse(
                raw_output=raw_output,
                agent_name=self._config.agent_name,
            )
        except ValidationError as exc:
            return self._failed_result(
                request=request,
                errors=(format_validation_error(exc),),
                warnings=context_result.warnings + rule_warnings,
            )
        except ValueError as exc:
            return self._failed_result(
                request=request,
                errors=(str(exc),),
                warnings=context_result.warnings + rule_warnings,
            )
        except Exception as exc:
            self._logger.exception("developer_agent_execution_failed")
            return self._failed_result(
                request=request,
                errors=(str(exc),),
                warnings=context_result.warnings + rule_warnings,
            )

        output_artifact = Artifact(
            id=f"{self._config.agent_name}-{request.execution_id}",
            kind=ArtifactKind.SOURCE_CODE,
            name="Developer Structured Output",
            producer_agent=self._config.agent_name,
            content=structured_output.model_dump_json(indent=2),
            metadata={"contract_kind": structured_output.contract_kind.value},
        )
        result = AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self._config.agent_name,
            status=AgentStatus.COMPLETED,
            summary=structured_output.summary,
            artifacts=structured_output.artifacts + (output_artifact,),
            metadata={
                "context_warnings": context_result.warnings + rule_warnings,
                "loaded_rule_files": tuple(sorted(required_rules)),
                "prompt_message_count": len(messages),
                "repository_analysis": repository_analysis.model_dump(mode="json"),
                "structured_output": structured_output.model_dump(mode="json"),
            },
        )
        self._logger.info("developer_agent_execution_completed", extra={"agent": self._config.agent_name})
        await self._telemetry_hook.emit(
            "developer_agent_execution_completed",
            {
                "agent": self._config.agent_name,
                "execution_id": str(request.execution_id),
                "status": result.status.value,
            },
        )
        return result

    @classmethod
    def from_agent_definition(
        cls,
        agent: AgentDefinition,
        output_contract: OutputContract,
        model_client: AgentModelClient,
    ) -> "DeveloperAgentRuntime":
        return cls(
            config=DeveloperRuntimeConfig(
                agent_name=agent.name,
                context_path=agent.context_path,
                repository_path=agent.context_path.parents[1],
                output_contract=output_contract,
            ),
            model_client=model_client,
        )

    def _load_required_rules(self) -> tuple[dict[str, str], tuple[str, ...]]:
        rules: dict[str, str] = {}
        warnings: list[str] = []
        for file_name in self._config.required_rule_files:
            path = self._config.context_path / file_name
            if not path.exists():
                warnings.append(f"Required developer rule file missing: {file_name}")
                continue
            rules[file_name] = path.read_text(encoding="utf-8")
        return rules, tuple(warnings)

    def _failed_result(
        self,
        request: AgentExecutionRequest,
        errors: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self._config.agent_name,
            status=AgentStatus.FAILED,
            errors=errors,
            metadata={"context_warnings": warnings},
        )
