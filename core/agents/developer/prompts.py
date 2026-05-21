"""Developer prompt composition."""

from core.agents.developer.contracts import DeveloperRuntimeConfig, RepositoryAnalysis
from core.contracts.context import AgentContext
from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompts import PromptMessage, PromptRole


class DeveloperPromptBuilder:
    """Builds developer prompts from dynamic context inputs."""

    async def build(
        self,
        request: AgentExecutionRequest,
        config: DeveloperRuntimeConfig,
        agent_context: AgentContext,
        repository_analysis: RepositoryAnalysis,
        required_rules: dict[str, str] | None = None,
    ) -> tuple[PromptMessage, ...]:
        system_sections = [
            self._identity_section(config),
            self._capability_section(config),
            self._boundary_section(),
            *config.additional_instructions,
        ]
        user_sections = [
            self._task_section(request),
            self._rules_section(agent_context, required_rules or {}),
            self._repository_section(repository_analysis),
            self._upstream_section(request),
            self._output_contract_section(config),
        ]
        return (
            PromptMessage(role=PromptRole.SYSTEM, content="\n\n".join(system_sections)),
            PromptMessage(role=PromptRole.USER, content="\n\n".join(user_sections)),
        )

    def _identity_section(self, config: DeveloperRuntimeConfig) -> str:
        return f"# Agent\n\nName: {config.agent_name}\nRole: developer"

    def _capability_section(self, config: DeveloperRuntimeConfig) -> str:
        capabilities = "\n".join(f"- {capability.value}" for capability in config.capabilities)
        return f"# Capabilities\n\n{capabilities}"

    def _boundary_section(self) -> str:
        return (
            "# Responsibility Boundary\n\n"
            "Operate only as the developer agent. Use BA stories and architecture context as inputs. "
            "Do not redefine requirements, architecture decisions, QA approval, documentation ownership, or PR creation ownership."
        )

    def _task_section(self, request: AgentExecutionRequest) -> str:
        return f"# Task\n\n{request.task.strip()}"

    def _rules_section(self, agent_context: AgentContext, required_rules: dict[str, str]) -> str:
        rendered = agent_context.render()
        required = "\n\n".join(
            f"## {file_name}\n\n{content.strip() or '[empty file]'}"
            for file_name, content in sorted(required_rules.items())
        )
        sections = ["# Loaded Developer Rules"]
        if required:
            sections.append(f"## Required Rule Files\n\n{required}")
        if rendered:
            sections.append(f"## Classified Context\n\n{rendered}")
        if len(sections) == 1:
            sections.append("None")
        return "\n\n".join(sections)

    def _repository_section(self, analysis: RepositoryAnalysis) -> str:
        files = "\n".join(f"- {item.path} ({item.size_bytes} bytes)" for item in analysis.files[:80])
        directories = "\n".join(f"- {item}" for item in analysis.directories[:80])
        languages = ", ".join(analysis.detected_languages) or "unknown"
        tests = "\n".join(f"- {item}" for item in analysis.test_paths[:40]) or "None detected"
        return (
            "# Repository Analysis\n\n"
            f"Root: {analysis.root_path}\n"
            f"Detected languages: {languages}\n\n"
            f"## Directories\n\n{directories or 'None detected'}\n\n"
            f"## Files\n\n{files or 'None detected'}\n\n"
            f"## Test Paths\n\n{tests}"
        )

    def _upstream_section(self, request: AgentExecutionRequest) -> str:
        artifacts = "\n".join(
            f"- {artifact.kind.value}: {artifact.name} from {artifact.producer_agent}"
            for artifact in request.upstream_artifacts
        )
        architecture_context = str(request.metadata.get("architecture_context", "")).strip()
        ba_stories = str(request.metadata.get("ba_stories", "")).strip()
        sections = ["# Upstream Inputs"]
        if architecture_context:
            sections.append(f"## Architecture Context\n\n{architecture_context}")
        if ba_stories:
            sections.append(f"## BA Stories\n\n{ba_stories}")
        if artifacts:
            sections.append(f"## Artifacts\n\n{artifacts}")
        if len(sections) == 1:
            sections.append("None")
        return "\n\n".join(sections)

    def _output_contract_section(self, config: DeveloperRuntimeConfig) -> str:
        return f"# Structured Output Contract\n\n{config.output_contract.model_dump_json(indent=2)}"
