from pathlib import Path

import pytest

from core.bootstrap import build_platform_foundation
from core.contracts.context import AgentContext, ContextSection, ContextSectionName
from core.contracts.memory import MemoryRecord, MemoryScope
from core.contracts.prompts import PromptBuildRequest, PromptRole


@pytest.mark.asyncio
async def test_foundation_discovers_agents_and_builds_available_workflow() -> None:
    foundation = await build_platform_foundation(Path.cwd())

    agent_names = {agent.name for agent in foundation.agents}

    assert {"ba", "architect", "developer", "qa", "pr"}.issubset(agent_names)
    assert foundation.workflow.agents == (
        "ba",
        "architect",
        "developer",
        "qa",
        "docs",
        "pr",
    )
    assert all(
        edge.source in foundation.workflow.agents and edge.target in foundation.workflow.agents
        for edge in foundation.workflow.edges
    )


@pytest.mark.asyncio
async def test_context_loader_keeps_agent_context_isolated() -> None:
    foundation = await build_platform_foundation(Path.cwd())
    ba_agent = next(agent for agent in foundation.agents if agent.name == "ba")

    context = await foundation.context_loader.load(ba_agent)
    rendered = context.render()

    assert context.agent_name == "ba"
    assert "SIEMPRE generar historias INVEST" in rendered
    assert "Principal Engineer" not in rendered


@pytest.mark.asyncio
async def test_prompt_builder_composes_structured_messages() -> None:
    foundation = await build_platform_foundation(Path.cwd())
    context = AgentContext(
        agent_name="ba",
        sections=(ContextSection(name=ContextSectionName.GENERAL),),
    )

    messages = await foundation.prompt_builder.build(
        PromptBuildRequest(
            agent_name="ba",
            task="Create user stories",
            context=context,
            output_contract="Return structured requirements.",
        )
    )

    assert [message.role for message in messages] == [PromptRole.SYSTEM, PromptRole.USER]
    assert "Active agent: ba." in messages[0].content
    assert "Create user stories" in messages[1].content


@pytest.mark.asyncio
async def test_memory_repository_respects_scope_and_agent_filters() -> None:
    foundation = await build_platform_foundation(Path.cwd())

    await foundation.memory_repository.put(
        MemoryRecord(
            scope=MemoryScope.AGENT,
            key="decision",
            value={"text": "BA owns functional requirements"},
            agent_name="ba",
        )
    )

    record = await foundation.memory_repository.get(
        key="decision",
        scope=MemoryScope.AGENT,
        agent_name="ba",
    )
    missing = await foundation.memory_repository.get(
        key="decision",
        scope=MemoryScope.AGENT,
        agent_name="developer",
    )

    assert record is not None
    assert record.value["text"] == "BA owns functional requirements"
    assert missing is None
