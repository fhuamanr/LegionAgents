"""Runtime prompt building."""

from abc import ABC, abstractmethod

from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompts import PromptMessage, PromptRole
from core.runtime.models import RuntimeExecutionContext


class PromptBuilder(ABC):
    """Builds dynamic prompts for isolated agent execution."""

    @abstractmethod
    async def build(self, context: RuntimeExecutionContext) -> tuple[PromptMessage, ...]:
        """Compose prompt messages."""


class RuntimePromptBuilder(PromptBuilder):
    """Default prompt builder for runtime agents."""

    async def build(self, context: RuntimeExecutionContext) -> tuple[PromptMessage, ...]:
        request = context.request
        config = context.agent_config

        system_sections = [
            "You are executing one isolated specialized agent in a multi-agent software delivery platform.",
            f"Agent name: {config.name}.",
            f"Agent role: {config.role}.",
            "Stay inside this agent boundary. Do not perform responsibilities owned by other agents.",
            "Return only a valid JSON object. Do not wrap it in Markdown unless the model provider forces it.",
            "The JSON object must satisfy the configured output schema.",
        ]
        system_sections.extend(config.system_instructions)
        system_sections.extend(config.additional_instructions)

        user_sections = [
            f"# Task\n\n{request.task.strip()}",
            f"# Output Schema\n\n{config.output_schema_name}",
        ]
        schema = config.metadata.get("output_json_schema")
        if schema:
            user_sections.append(f"# Required JSON Schema\n\n```json\n{schema}\n```")

        governance_text = context.agent_context.metadata.get("governance_text")
        if governance_text:
            user_sections.append(f"# Inherited Governance Policy\n\n{governance_text}")

        rendered_context = context.agent_context.render()
        if rendered_context:
            user_sections.append(f"# Isolated Markdown Rules And Context\n\n{rendered_context}")

        artifact_text = self._render_upstream_artifacts(request)
        if artifact_text:
            user_sections.append(f"# Upstream Artifacts\n\n{artifact_text}")

        if context.tools:
            user_sections.append("# Available Tools\n\n" + "\n".join(f"- {name}" for name in context.tools))

        return (
            PromptMessage(role=PromptRole.SYSTEM, content="\n\n".join(system_sections)),
            PromptMessage(role=PromptRole.USER, content="\n\n".join(user_sections)),
        )

    def _render_upstream_artifacts(self, request: AgentExecutionRequest) -> str:
        return "\n".join(
            f"- {artifact.kind.value}: {artifact.name} from {artifact.producer_agent}"
            for artifact in request.upstream_artifacts
        )
