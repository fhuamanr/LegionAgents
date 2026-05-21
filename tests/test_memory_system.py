from uuid import uuid4

import pytest

from core.contracts.memory import (
    MemoryNamespace,
    MemoryQuery,
    MemoryScope,
    VectorMemoryQuery,
)
from core.memory import InMemoryMemoryRepository, MemorySystem, NamespacedMemoryRepository


@pytest.mark.asyncio
async def test_short_term_memory_is_thread_and_agent_isolated() -> None:
    memory = MemorySystem()

    await memory.short_term.remember(
        key="turn",
        value={"text": "ba note"},
        thread_id="thread-1",
        agent_name="ba",
    )
    await memory.short_term.remember(
        key="turn",
        value={"text": "dev note"},
        thread_id="thread-1",
        agent_name="developer",
    )
    await memory.short_term.remember(
        key="turn",
        value={"text": "other thread"},
        thread_id="thread-2",
        agent_name="ba",
    )

    records = await memory.short_term.recall(thread_id="thread-1", agent_name="ba")

    assert len(records) == 1
    assert records[0].value["text"] == "ba note"


@pytest.mark.asyncio
async def test_long_term_memory_supports_namespace_queries() -> None:
    memory = MemorySystem()

    await memory.long_term.remember(
        key="decision",
        value={"text": "Use clean architecture"},
        scope=MemoryScope.GLOBAL,
        importance=0.9,
        tags=("architecture",),
    )

    records = await memory.long_term.recall(
        MemoryQuery(
            scope=MemoryScope.GLOBAL,
            tags=("architecture",),
        )
    )

    assert len(records) == 1
    assert records[0].namespace == MemoryNamespace.LONG_TERM
    assert records[0].importance == 0.9


@pytest.mark.asyncio
async def test_execution_history_adr_bug_and_checkpoints_are_retrievable() -> None:
    memory = MemorySystem()
    workflow_id = uuid4()

    await memory.execution_history.append(
        event_name="developer_completed",
        value={"status": "completed"},
        workflow_id=workflow_id,
        agent_name="developer",
    )
    await memory.adr.record(
        key="ADR-1",
        title="Runtime isolation",
        value={"decision": "Keep agent memory isolated"},
        workflow_id=workflow_id,
        status="accepted",
    )
    await memory.bugs.record(
        key="BUG-1",
        title="Validation failed",
        value={"error": "schema mismatch"},
        workflow_id=workflow_id,
        agent_name="qa",
        severity="high",
    )
    await memory.checkpoints.put_checkpoint(
        thread_id="thread-1",
        checkpoint_id="cp-1",
        state={"active_agent": "developer"},
    )

    history = await memory.execution_history.list_for_workflow(workflow_id)
    adrs = await memory.adr.search(MemoryQuery(workflow_id=workflow_id))
    bugs = await memory.bugs.search(MemoryQuery(workflow_id=workflow_id))
    checkpoint = await memory.checkpoints.get_latest("thread-1")

    assert history[0].event_name == "developer_completed"
    assert adrs[0].status == "accepted"
    assert bugs[0].severity == "high"
    assert checkpoint is not None
    assert checkpoint.value["active_agent"] == "developer"


@pytest.mark.asyncio
async def test_vector_memory_supports_text_and_embedding_search() -> None:
    memory = MemorySystem()

    await memory.vector.remember(
        key="doc-1",
        text="LangGraph checkpoint memory for developer agents",
        value={"source": "note"},
        scope=MemoryScope.GLOBAL,
        embedding=(1.0, 0.0),
    )
    await memory.vector.remember(
        key="doc-2",
        text="Unrelated documentation",
        value={"source": "note"},
        scope=MemoryScope.GLOBAL,
        embedding=(0.0, 1.0),
    )

    text_results = await memory.vector.search(VectorMemoryQuery(text="checkpoint developer"))
    vector_results = await memory.vector.search(
        VectorMemoryQuery(text="ignored", embedding=(1.0, 0.0))
    )

    assert text_results[0].record.key == "doc-1"
    assert vector_results[0].record.key == "doc-1"


@pytest.mark.asyncio
async def test_namespaced_repository_binds_namespace() -> None:
    repository = InMemoryMemoryRepository()
    namespaced = NamespacedMemoryRepository(repository, MemoryNamespace.LONG_TERM)

    await namespaced.put(
        await MemorySystem(repository).short_term.remember(
            key="temporary",
            value={"text": "stored"},
            thread_id="thread-1",
        )
    )

    records = await namespaced.query()

    assert records
    assert all(record.namespace == MemoryNamespace.LONG_TERM for record in records)
