"""Developer agent runtime package."""

__all__ = ["DeveloperAgentRuntime"]


def __getattr__(name: str) -> object:
    """Load executable runtime lazily to keep repository analysis importable."""

    if name == "DeveloperAgentRuntime":
        from core.agents.developer.runtime import DeveloperAgentRuntime

        return DeveloperAgentRuntime
    raise AttributeError(name)

