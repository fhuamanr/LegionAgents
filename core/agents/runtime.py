"""Base runtime abstractions for specialized agents."""

from abc import ABC, abstractmethod

from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.prompts import PromptMessage


class AgentModelClient(ABC):
    """Boundary for LLM/model execution."""

    @abstractmethod
    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        """Return a raw model response for composed messages."""


class AgentRuntime(ABC):
    """Base runtime contract for specialized agents."""

    @abstractmethod
    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        """Execute a specialized agent request."""

