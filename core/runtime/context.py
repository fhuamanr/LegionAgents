"""Runtime context assembly."""

from abc import ABC, abstractmethod

from core.context import FileSystemAgentContextLoader
from core.contracts.context import AgentContext, ContextLoadRequest
from core.contracts.execution import AgentExecutionRequest
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

