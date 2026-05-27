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
        metadata = request.metadata
        local_compact_mode = bool(metadata.get("local_lm_studio_safe_mode", False) or metadata.get("compact_mode_enabled", False))
        parser_strategy = str(metadata.get("parser_strategy", "")).strip().lower()
        require_json = parser_strategy not in {"markdown_sections"}
        enable_governance = bool(metadata.get("enable_governance_context", not local_compact_mode))
        enable_examples = bool(metadata.get("enable_examples", not local_compact_mode))
        enable_repo_context = bool(metadata.get("enable_repo_context", not local_compact_mode))
        enable_diagrams = bool(metadata.get("enable_diagrams", not local_compact_mode))

        system_sections = [
            "You are executing one isolated specialized agent in a multi-agent software delivery platform.",
            f"Agent name: {config.name}.",
            f"Agent role: {config.role}.",
            "Stay inside this agent boundary. Do not perform responsibilities owned by other agents.",
            "Return only the final answer. Do not include reasoning.",
        ]
        if require_json:
            system_sections.extend(
                [
                    "Return only a valid JSON object. Do not wrap it in Markdown unless the model provider forces it.",
                    "The JSON object must satisfy the configured output schema.",
                ]
            )
            if config.name == "developer":
                system_sections.extend(
                    [
                        "Developer output contract is strict: include agent_name, summary, code_changes, tests.",
                        "Each code_changes item must include path, change_type, description, content.",
                        "Each tests item must include path, test_type, description, content.",
                    ]
                )
            if config.name == "qa":
                system_sections.extend(
                    [
                        "QA output contract is strict: include agent_name and summary at minimum.",
                        "Keep output concise with max 3 findings and max 3 recommendations.",
                        "Return strict JSON only.",
                    ]
                )
        elif parser_strategy == "markdown_sections":
            system_sections.append(
                "Return compact markdown sections only using the required section headers. No code fences."
            )
        system_sections.extend(config.system_instructions)
        system_sections.extend(config.additional_instructions)

        user_sections = [
            f"# Task\n\n{request.task.strip()}",
            f"# Output Schema\n\n{config.output_schema_name}",
        ]
        schema = config.metadata.get("output_json_schema")
        if schema and require_json and not local_compact_mode:
            user_sections.append(f"# Required JSON Schema\n\n```json\n{schema}\n```")
        if config.name == "developer":
            user_sections.append(
                "# Developer Output Requirements\n\n"
                "Required minimal JSON shape:\n"
                '{\n'
                '  "agent_name": "developer",\n'
                '  "summary": "Concise summary.",\n'
                '  "code_changes": [{"path":"src/file.tsx","change_type":"create","description":"...","content":"..."}],\n'
                '  "tests": [{"path":"src/file.test.tsx","test_type":"unit","description":"...","content":"..."}],\n'
                '  "handoff": "Short handoff for QA."\n'
                "}\n"
                "Local compact mode limits: max 3 code_changes and max 3 tests."
            )
        if config.name == "qa":
            user_sections.append(
                "# QA Output Requirements\n\n"
                "Required minimal JSON shape:\n"
                '{\n'
                '  "agent_name": "qa",\n'
                '  "summary": "Short QA evaluation summary.",\n'
                '  "test_results": [],\n'
                '  "issues_found": [],\n'
                '  "recommendations": [],\n'
                '  "status": "passed"\n'
                "}\n"
                "If no tests are available, still provide agent_name and summary."
            )

        governance_text = context.agent_context.metadata.get("governance_text")
        if governance_text and enable_governance:
            user_sections.append(
                "# Runtime-Enforced Governance Policy\n\n"
                "These gravity, anti-gravity, forbidden, and architecture rules are not advisory. "
                "The runtime validates generated output against them and rejects invalid output.\n\n"
                f"{governance_text if not local_compact_mode else self._compress_text(governance_text, 450)}"
            )

        rendered_context = context.agent_context.render() if (enable_repo_context or enable_examples or enable_diagrams) else ""
        if rendered_context:
            compact_context = rendered_context
            if local_compact_mode:
                compact_context = self._compress_text(rendered_context, 900)
            user_sections.append(f"# Isolated Markdown Rules And Context\n\n{compact_context}")

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

    def _compress_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n\n[Context compressed for compact mode.]"
