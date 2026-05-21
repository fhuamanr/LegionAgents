"""Prompt composition strategies."""

from abc import ABC, abstractmethod

from core.contracts.prompts import PromptBuildRequest, PromptMessage, PromptRole


class PromptBuilder(ABC):
    """Builds structured messages for one agent execution."""

    @abstractmethod
    async def build(self, request: PromptBuildRequest) -> tuple[PromptMessage, ...]:
        """Compose prompt messages."""


class DefaultPromptBuilder(PromptBuilder):
    """Default modular prompt builder.

    The builder keeps platform instructions, agent context, upstream artifacts,
    and task intent as explicit sections instead of flattening all agents into
    one shared prompt.
    """

    async def build(self, request: PromptBuildRequest) -> tuple[PromptMessage, ...]:
        system_sections = [
            "You are executing one specialized agent in an enterprise multi-agent software delivery platform.",
            f"Active agent: {request.agent_name}.",
            "Preserve the agent boundary and do not perform responsibilities owned by other agents.",
        ]
        if request.output_contract:
            system_sections.append(f"Output contract:\n{request.output_contract.strip()}")
        system_sections.extend(request.additional_instructions)

        user_sections = [f"# Task\n\n{request.task.strip()}"]
        context = request.context.render()
        if context:
            user_sections.append(f"# Isolated Agent Context\n\n{context}")
        if request.upstream_artifacts:
            artifacts = "\n".join(
                f"- {artifact.kind}: {artifact.name} from {artifact.producer_agent}"
                for artifact in request.upstream_artifacts
            )
            user_sections.append(f"# Upstream Artifacts\n\n{artifacts}")

        return (
            PromptMessage(role=PromptRole.SYSTEM, content="\n\n".join(system_sections)),
            PromptMessage(role=PromptRole.USER, content="\n\n".join(user_sections)),
        )

