"""Agent registry implementations."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.contracts.agents import AgentDefinition


class AgentRegistry(ABC):
    """Registry for discovering available agents."""

    @abstractmethod
    async def list_agents(self) -> tuple[AgentDefinition, ...]:
        """Return all enabled agent definitions."""

    @abstractmethod
    async def get_agent(self, name: str) -> AgentDefinition:
        """Return one agent definition by name."""


class FileSystemAgentRegistry(AgentRegistry):
    """Discovers agents from immediate subdirectories in an agents root."""

    def __init__(
        self,
        agents_root: Path,
        dependencies: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._agents_root = agents_root
        self._dependencies = dependencies or {}

    async def list_agents(self) -> tuple[AgentDefinition, ...]:
        if not self._agents_root.exists():
            return tuple()

        agents: list[AgentDefinition] = []
        for path in sorted(self._agents_root.iterdir()):
            if not path.is_dir():
                continue
            agents.append(
                AgentDefinition(
                    name=path.name,
                    role=path.name,
                    context_path=path,
                    depends_on=self._dependencies.get(path.name, tuple()),
                )
            )
        return tuple(agents)

    async def get_agent(self, name: str) -> AgentDefinition:
        for agent in await self.list_agents():
            if agent.name == name:
                return agent
        raise KeyError(f"Agent not found: {name}")

