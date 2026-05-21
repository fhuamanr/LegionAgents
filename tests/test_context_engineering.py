from pathlib import Path

import pytest

from core.context_engineering import (
    ContextEngineeringConfig,
    ContextEngineeringEngine,
    ContextEngineeringRequest,
    MemoryContextProvider,
)
from core.context_engineering.models import ContextItemSource
from core.contracts.memory import MemoryScope
from core.memory import MemorySystem


@pytest.mark.asyncio
async def test_context_engineering_builds_agent_specific_context_with_summaries() -> None:
    engine = ContextEngineeringEngine()

    result = await engine.build(
        ContextEngineeringRequest(
            agent_name="developer",
            task="Implement runtime",
            agent_context_path=Path.cwd() / "agents" / "developer",
            repository_path=Path.cwd(),
            architecture_context="Use Clean Architecture.\nKeep orchestration separate.",
            upstream_context=("BA story: user needs runtime execution.",),
            config=ContextEngineeringConfig(max_token_hint=5000),
        )
    )

    rendered = result.context.render()

    assert result.context.agent_name == "developer"
    assert result.context.metadata["engineered"] is True
    assert "SIEMPRE agregar logging" in rendered
    assert "Repository root:" in rendered
    assert "Use Clean Architecture." in rendered
    assert "BA story" in rendered
    assert "SIEMPRE validar criterios" not in rendered


@pytest.mark.asyncio
async def test_context_engineering_uses_memory_without_agent_leakage() -> None:
    memory = MemorySystem()
    await memory.long_term.remember(
        key="developer-note",
        value={"text": "Developer owns DTO implementation details."},
        scope=MemoryScope.AGENT,
        agent_name="developer",
    )
    await memory.long_term.remember(
        key="qa-note",
        value={"text": "QA owns validation evidence."},
        scope=MemoryScope.AGENT,
        agent_name="qa",
    )
    await memory.vector.remember(
        key="developer-vector",
        text="Developer runtime should keep prompts modular.",
        value={"source": "memory"},
        scope=MemoryScope.AGENT,
        agent_name="developer",
    )

    engine = ContextEngineeringEngine(memory_provider=MemoryContextProvider(memory))
    result = await engine.build(
        ContextEngineeringRequest(
            agent_name="developer",
            task="runtime prompts",
            agent_context_path=Path.cwd() / "agents" / "developer",
            config=ContextEngineeringConfig(enable_repository_summary=False),
        )
    )
    rendered = result.context.render()

    assert "Developer owns DTO implementation details" in rendered
    assert "Developer runtime should keep prompts modular" in rendered
    assert "QA owns validation evidence" not in rendered


@pytest.mark.asyncio
async def test_context_engineering_compresses_deduplicates_and_applies_budget() -> None:
    repeated = "Important implementation note.\n\n" * 200
    engine = ContextEngineeringEngine()

    result = await engine.build(
        ContextEngineeringRequest(
            agent_name="developer",
            task="Budget context",
            agent_context_path=Path.cwd() / "agents" / "developer",
            upstream_context=(repeated, repeated),
            config=ContextEngineeringConfig(
                max_token_hint=350,
                reserved_output_token_hint=50,
                enable_repository_summary=False,
                enable_architecture_summary=False,
                item_token_soft_limit=200,
            ),
        )
    )

    upstream_items = [
        item
        for item in result.selected_items + result.dropped_items
        if item.source == ContextItemSource.UPSTREAM
    ]

    assert result.token_hint <= 300
    assert len(upstream_items) == 1
    assert upstream_items[0].metadata.get("compressed") is True
    assert result.dropped_items


@pytest.mark.asyncio
async def test_context_engineering_can_disable_unnecessary_repository_loading() -> None:
    engine = ContextEngineeringEngine()

    result = await engine.build(
        ContextEngineeringRequest(
            agent_name="qa",
            task="Validate without repo summary",
            agent_context_path=Path.cwd() / "agents" / "qa",
            repository_path=Path.cwd(),
            config=ContextEngineeringConfig(enable_repository_summary=False),
        )
    )

    assert all(
        item.source != ContextItemSource.REPOSITORY_SUMMARY
        for item in result.selected_items
    )
