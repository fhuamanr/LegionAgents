from uuid import UUID

import pytest

from core.contracts.agents import AgentStatus
from core.graph import (
    DEFAULT_DELIVERY_SEQUENCE,
    InMemoryWorkflowExecutionRepository,
    LangGraphExecutionRuntime,
    WorkflowRunStatus,
)


@pytest.mark.asyncio
async def test_real_workflow_runtime_executes_full_delivery_sequence() -> None:
    repository = InMemoryWorkflowExecutionRepository()
    runtime = LangGraphExecutionRuntime(repository=repository)

    result = await runtime.start("Deliver executable orchestration")

    assert result.status == WorkflowRunStatus.COMPLETED
    assert isinstance(result.execution_id, UUID)
    latest = await repository.latest_checkpoint(result.execution_id)
    assert latest is not None
    assert latest.status == WorkflowRunStatus.COMPLETED
    assert tuple(latest.state.agent_states) == DEFAULT_DELIVERY_SEQUENCE
    assert all(
        snapshot.status == AgentStatus.COMPLETED
        for snapshot in latest.state.agent_states.values()
    )
    assert tuple(artifact.producer_agent for artifact in latest.state.artifacts) == DEFAULT_DELIVERY_SEQUENCE


@pytest.mark.asyncio
async def test_real_workflow_runtime_routes_qa_rejection_back_to_developer() -> None:
    runtime = LangGraphExecutionRuntime(max_qa_rejection_loops=2)

    result = await runtime.start(
        "Deliver workflow with QA loop",
        metadata={"force_qa_rejections": 1},
    )

    latest = await runtime.repository.latest_checkpoint(result.execution_id)

    assert result.status == WorkflowRunStatus.COMPLETED
    assert latest is not None
    assert latest.state.metadata["qa_rejection_count"] == 1
    assert latest.state.agent_states["developer"].attempt == 2
    assert latest.state.agent_states["qa"].attempt == 2


@pytest.mark.asyncio
async def test_real_workflow_runtime_persists_checkpoints_and_recovers() -> None:
    repository = InMemoryWorkflowExecutionRepository()
    runtime = LangGraphExecutionRuntime(repository=repository)

    paused = await runtime.start(
        "Recover executable workflow",
        metadata={"pause_after_agent": "architect"},
    )
    paused_record = await repository.get(paused.execution_id)

    assert paused.status == WorkflowRunStatus.PAUSED
    assert paused_record.next_agent == "developer"
    assert paused_record.checkpoints

    resumed = await runtime.recover(paused.execution_id)
    latest = await repository.latest_checkpoint(paused.execution_id)

    assert resumed.status == WorkflowRunStatus.COMPLETED
    assert latest is not None
    assert tuple(latest.state.agent_states) == DEFAULT_DELIVERY_SEQUENCE


@pytest.mark.asyncio
async def test_real_workflow_runtime_cancels_running_execution() -> None:
    repository = InMemoryWorkflowExecutionRepository()

    async def cancel_when_developer_starts(event_name: str, state: dict[str, object]) -> None:
        if event_name == "agent_started" and state.get("next_agent") == "developer":
            await repository.cancel(state["execution_id"], "manual cancellation requested")

    runtime = LangGraphExecutionRuntime(
        repository=repository,
        event_hook=cancel_when_developer_starts,
    )

    result = await runtime.start("Cancel executable workflow")
    latest = await repository.latest_checkpoint(result.execution_id)

    assert result.status == WorkflowRunStatus.CANCELLED
    assert latest is not None
    assert latest.status == WorkflowRunStatus.CANCELLED
    assert "docs" not in latest.state.agent_states
    assert "pr" not in latest.state.agent_states
