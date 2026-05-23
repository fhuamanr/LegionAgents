"""Agent runtime package."""

from core.agents.model_clients import OpenAIChatModelClient
from core.agents.runtime import AgentModelClient, AgentRuntime

__all__ = [
    "AgentModelClient",
    "AgentRuntime",
    "LLMStructuredAgentRuntime",
    "OpenAIChatModelClient",
    "QAAgentRuntime",
    "build_llm_agent_runtimes",
]


def __getattr__(name: str) -> object:
    """Load heavy runtime exports lazily to avoid package-level import cycles."""

    if name in {"LLMStructuredAgentRuntime", "build_llm_agent_runtimes"}:
        from core.agents.llm_runtime import LLMStructuredAgentRuntime, build_llm_agent_runtimes

        return {
            "LLMStructuredAgentRuntime": LLMStructuredAgentRuntime,
            "build_llm_agent_runtimes": build_llm_agent_runtimes,
        }[name]
    if name == "QAAgentRuntime":
        from core.agents.qa import QAAgentRuntime

        return QAAgentRuntime
    raise AttributeError(name)
