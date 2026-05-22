from uuid import uuid4

import pytest

from core.contracts.memory import MemoryQuery, MemoryScope
from core.contracts.memory_intelligence import (
    SemanticIndexRequest,
    SemanticMemoryKind,
    SemanticRetrievalQuery,
)
from core.memory import (
    MemoryIntelligenceSystem,
    MemorySystem,
    QdrantSemanticVectorStore,
    QdrantVectorStoreConfig,
)


@pytest.mark.asyncio
async def test_memory_intelligence_retrieves_agent_and_shared_semantic_memory() -> None:
    memory = MemorySystem()

    await memory.intelligence.learn_historical_bug(
        SemanticIndexRequest(
            key="BUG-auth-token",
            text="Historical bug: API client retry loop broke authentication token refresh during browser QA.",
            kind=SemanticMemoryKind.HISTORICAL_BUG,
            scope=MemoryScope.GLOBAL,
            tags=("auth", "qa"),
        )
    )
    await memory.intelligence.learn_coding_pattern(
        SemanticIndexRequest(
            key="DEV-pattern-fetch",
            text="Developer agent should isolate API client retries behind a typed service boundary.",
            kind=SemanticMemoryKind.CODING_PATTERN,
            scope=MemoryScope.AGENT,
            agent_name="developer",
            tags=("api", "retry"),
        )
    )

    results = await memory.intelligence.retrieve(
        SemanticRetrievalQuery(
            text="developer retry API client boundary",
            agent_name="developer",
            include_shared=True,
            limit=3,
        )
    )

    keys = [result.document.key for result in results]
    assert keys[0] == "DEV-pattern-fetch"
    assert "agent_specific_match" in results[0].reasons
    assert "BUG-auth-token" in keys


@pytest.mark.asyncio
async def test_memory_intelligence_indexes_execution_history_records() -> None:
    memory = MemorySystem()
    workflow_id = uuid4()

    await memory.execution_history.append(
        event_name="qa_failed",
        value={"text": "QA failed because checkout submit button was disabled."},
        workflow_id=workflow_id,
        agent_name="qa",
        tags=("checkout", "qa"),
    )

    summary = await memory.intelligence.index_execution_history(
        MemoryQuery(workflow_id=workflow_id)
    )
    results = await memory.intelligence.retrieve(
        SemanticRetrievalQuery(
            text="checkout disabled submit button",
            kinds=(SemanticMemoryKind.EXECUTION_HISTORY,),
            agent_name="qa",
            workflow_id=workflow_id,
        )
    )

    assert summary.indexed_count == 1
    assert results[0].document.kind == SemanticMemoryKind.EXECUTION_HISTORY
    assert results[0].document.workflow_id == workflow_id


@pytest.mark.asyncio
async def test_memory_intelligence_supports_injected_store_and_qdrant_boundary() -> None:
    system = MemoryIntelligenceSystem()

    await system.learn_architectural_decision(
        SemanticIndexRequest(
            key="ADR-context-isolation",
            text="Architecture decision: keep agent context isolated and share only contracts.",
            scope=MemoryScope.GLOBAL,
            tags=("architecture",),
        )
    )
    results = await system.retrieve(
        SemanticRetrievalQuery(
            text="isolated agent context contracts",
            kinds=(SemanticMemoryKind.ARCHITECTURAL_DECISION,),
        )
    )

    assert results
    assert results[0].document.key == "ADR-context-isolation"

    qdrant = QdrantSemanticVectorStore(
        QdrantVectorStoreConfig(collection_name="test_memory", vector_size=64)
    )
    with pytest.raises(NotImplementedError):
        await qdrant.search(SemanticRetrievalQuery(text="anything"), embedding=(0.0,) * 64)
