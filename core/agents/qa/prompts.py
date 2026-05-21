"""QA prompt composition."""

from core.agents.qa.contracts import QARuntimeConfig
from core.contracts.context import AgentContext
from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompts import PromptMessage, PromptRole


class QAPromptBuilder:
    """Builds QA prompts from dynamic rule and execution inputs."""

    async def build(
        self,
        request: AgentExecutionRequest,
        config: QARuntimeConfig,
        agent_context: AgentContext,
        required_rules: dict[str, str],
    ) -> tuple[PromptMessage, ...]:
        system_sections = [
            self._identity_section(config),
            self._capability_section(config),
            self._boundary_section(),
            *config.additional_instructions,
        ]
        user_sections = [
            self._task_section(request),
            self._rules_section(agent_context, required_rules),
            self._upstream_section(request),
            self._automation_section(),
            self._output_contract_section(config),
        ]
        return (
            PromptMessage(role=PromptRole.SYSTEM, content="\n\n".join(system_sections)),
            PromptMessage(role=PromptRole.USER, content="\n\n".join(user_sections)),
        )

    def _identity_section(self, config: QARuntimeConfig) -> str:
        return f"# Agent\n\nName: {config.agent_name}\nRole: qa"

    def _capability_section(self, config: QARuntimeConfig) -> str:
        capabilities = "\n".join(f"- {capability.value}" for capability in config.capabilities)
        return f"# Capabilities\n\n{capabilities}"

    def _boundary_section(self) -> str:
        return (
            "# Responsibility Boundary\n\n"
            "Operate only as the QA agent. Validate acceptance criteria, generate evidence, "
            "classify severity, and report bugs. Do not implement product code or approve PR ownership."
        )

    def _task_section(self, request: AgentExecutionRequest) -> str:
        return f"# Task\n\n{request.task.strip()}"

    def _rules_section(self, agent_context: AgentContext, required_rules: dict[str, str]) -> str:
        required = "\n\n".join(
            f"## {file_name}\n\n{content.strip() or '[empty file]'}"
            for file_name, content in sorted(required_rules.items())
        )
        rendered = agent_context.render()
        sections = ["# Loaded QA Rules"]
        if required:
            sections.append(f"## Required Rule Files\n\n{required}")
        if rendered:
            sections.append(f"## Classified Context\n\n{rendered}")
        if len(sections) == 1:
            sections.append("None")
        return "\n\n".join(sections)

    def _upstream_section(self, request: AgentExecutionRequest) -> str:
        artifacts = "\n".join(
            f"- {artifact.kind.value}: {artifact.name} from {artifact.producer_agent}"
            for artifact in request.upstream_artifacts
        )
        acceptance = str(request.metadata.get("acceptance_criteria", "")).strip()
        implementation = str(request.metadata.get("implementation_context", "")).strip()
        sections = ["# Upstream Inputs"]
        if acceptance:
            sections.append(f"## Acceptance Criteria\n\n{acceptance}")
        if implementation:
            sections.append(f"## Implementation Context\n\n{implementation}")
        if artifacts:
            sections.append(f"## Artifacts\n\n{artifacts}")
        if len(sections) == 1:
            sections.append("None")
        return "\n\n".join(sections)

    def _automation_section(self) -> str:
        return (
            "# Automation Expectations\n\n"
            "When browser evidence is needed, describe Playwright or Selenium steps and screenshot evidence. "
            "When code validation is needed, propose unit and integration tests with commands."
        )

    def _output_contract_section(self, config: QARuntimeConfig) -> str:
        return f"# Structured Output Contract\n\n{config.output_contract.model_dump_json(indent=2)}"

