"""Composition helpers for the platform foundation."""

from pathlib import Path

from core.context import FileSystemAgentContextLoader, FileSystemAgentRegistry
from core.contracts.agents import AgentDefinition
from core.contracts.workflow import WorkflowDefinition
from core.graph.factory import build_default_delivery_workflow
from core.memory import InMemoryMemoryRepository, MemoryRepository
from core.prompts import DefaultPromptBuilder, PromptBuilder


class PlatformFoundation:
    """Container for foundational services.

    This is intentionally lightweight so FastAPI, CLI, and background workers
    can each wire their own infrastructure later.
    """

    def __init__(
        self,
        agents: tuple[AgentDefinition, ...],
        workflow: WorkflowDefinition,
        prompt_builder: PromptBuilder,
        memory_repository: MemoryRepository,
        context_loader: FileSystemAgentContextLoader,
    ) -> None:
        self.agents = agents
        self.workflow = workflow
        self.prompt_builder = prompt_builder
        self.memory_repository = memory_repository
        self.context_loader = context_loader


async def build_platform_foundation(project_root: Path) -> PlatformFoundation:
    """Build default foundational services from a project root."""

    dependencies = {
        "architect": ("ba",),
        "developer": ("architect",),
        "qa": ("developer",),
        "docs": ("developer", "qa"),
        "pr": ("docs",),
    }
    registry = FileSystemAgentRegistry(
        agents_root=project_root / "agents",
        dependencies=dependencies,
    )
    agents = await registry.list_agents()
    workflow = build_default_delivery_workflow(tuple(agent.name for agent in agents))

    return PlatformFoundation(
        agents=agents,
        workflow=workflow,
        prompt_builder=DefaultPromptBuilder(),
        memory_repository=InMemoryMemoryRepository(),
        context_loader=FileSystemAgentContextLoader(),
    )

