"""Runtime context assembly."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.context import FileSystemAgentContextLoader
from core.contracts.context import AgentContext, ContextLoadRequest
from core.contracts.execution import AgentExecutionRequest
from core.governance import AgentGovernanceEngine
from core.runtime.models import RuntimeAgentConfig


class ContextAssembler(ABC):
    """Assembles isolated runtime context for an agent."""

    @abstractmethod
    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        """Build an isolated context package for the request."""


class MarkdownRuleContextAssembler(ContextAssembler):
    """Loads markdown and Mermaid rule files from an agent context directory."""

    def __init__(self, context_loader: FileSystemAgentContextLoader | None = None) -> None:
        self._context_loader = context_loader or FileSystemAgentContextLoader()

    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        result = await self._context_loader.load_request(
            ContextLoadRequest(
                agent_name=config.name,
                root_path=config.context_path,
                max_token_hint=config.max_context_token_hint,
            )
        )
        return result.context.model_copy(
            update={
                "metadata": {
                    **result.context.metadata,
                    "context_warnings": result.warnings,
                    "requested_agent": request.agent_name,
                }
            }
        )


class GovernanceRuntimeContextAssembler(MarkdownRuleContextAssembler):
    """Loads agent markdown context plus inherited governance policy metadata."""

    def __init__(
        self,
        context_loader: FileSystemAgentContextLoader | None = None,
        governance_engine: AgentGovernanceEngine | None = None,
        agents_root: Path | None = None,
        standards_root: Path | None = None,
    ) -> None:
        super().__init__(context_loader=context_loader)
        self._governance_engine = governance_engine
        self._agents_root = agents_root
        self._standards_root = standards_root

    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        context = await super().assemble(request, config)
        engine = self._governance_engine or self._build_engine(config.context_path)
        policy = await engine.effective_policy_for_agent(config.name)
        governance_text = "\n".join(
            f"- [{rule.priority.value}/{rule.effect.value}/{rule.category.value}] {rule.description}"
            for rule in policy.rules
        )
        return context.model_copy(
            update={
                "metadata": {
                    **context.metadata,
                    "governance_policy_name": policy.name,
                    "governance_rule_count": len(policy.rules),
                    "governance_rules": tuple(rule.model_dump(mode="json") for rule in policy.rules),
                    "governance_text": governance_text,
                }
            }
        )

    def _build_engine(self, context_path: Path) -> AgentGovernanceEngine:
        agents_root = self._agents_root or context_path.parent
        standards_root = self._standards_root or agents_root / "standards"
        return AgentGovernanceEngine(agents_root=agents_root, standards_root=standards_root)
