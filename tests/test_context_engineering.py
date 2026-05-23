from pathlib import Path

import pytest

from core.context_engineering import (
    ContextEngineeringConfig,
    ContextEngineeringEngine,
    ContextEngineeringRequest,
    MemoryContextProvider,
)
from core.context_engineering.models import ContextItemSource
from core.contracts.execution import AgentExecutionRequest
from core.runtime.context import GovernanceRuntimeContextAssembler
from core.runtime.models import RuntimeAgentConfig
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


@pytest.mark.asyncio
async def test_context_engineering_selects_semantic_repository_files() -> None:
    engine = ContextEngineeringEngine()

    result = await engine.build(
        ContextEngineeringRequest(
            agent_name="developer",
            task="Implement context engineering runtime with token budgeting",
            agent_context_path=Path.cwd() / "agents" / "developer",
            repository_path=Path.cwd(),
            config=ContextEngineeringConfig(
                max_token_hint=2500,
                reserved_output_token_hint=500,
                selected_repository_file_limit=4,
            ),
        )
    )

    repository_files = [
        item
        for item in result.selected_items
        if item.source == ContextItemSource.REPOSITORY_FILE
    ]

    assert repository_files
    assert any("core/context_engineering/" in str(item.metadata["path"]) for item in repository_files)
    assert result.token_hint <= result.metadata["token_budget"]


@pytest.mark.asyncio
async def test_runtime_assembler_uses_engineered_isolated_context() -> None:
    assembler = GovernanceRuntimeContextAssembler()

    context = await assembler.assemble(
        AgentExecutionRequest(
            agent_name="developer",
            task="Implement semantic context selection",
            metadata={"repository_path": str(Path.cwd())},
        ),
        RuntimeAgentConfig(
            name="developer",
            role="software developer",
            context_path=Path.cwd() / "agents" / "developer",
            max_context_token_hint=2200,
            metadata={
                "reserved_output_token_hint": 500,
                "selected_repository_file_limit": 3,
            },
        ),
    )

    telemetry = context.metadata["context_engineering"]

    assert context.agent_name == "developer"
    assert telemetry["engineered"] is True
    assert telemetry["token_hint"] <= telemetry["token_budget"]
    assert any("repository-file-" in item_id for item_id in telemetry["selected_items"])
    assert "SIEMPRE validar criterios" not in context.render()
