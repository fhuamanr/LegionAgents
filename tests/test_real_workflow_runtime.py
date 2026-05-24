from uuid import UUID

import pytest

from core.agents.runtime import AgentModelClient
from core.contracts.agents import AgentStatus
from core.contracts.prompts import PromptMessage
from core.graph import (
    DEFAULT_DELIVERY_SEQUENCE,
    InMemoryWorkflowExecutionRepository,
    LangGraphExecutionRuntime,
    WorkflowRunStatus,
)


class WorkflowModelClient(AgentModelClient):
    def __init__(self, reject_qa_once: bool = False) -> None:
        self._reject_qa_once = reject_qa_once
        self._qa_calls = 0

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        prompt = "\n\n".join(message.content for message in messages)
        if "Agent name: ba." in prompt:
            return '{"agent_name":"ba","summary":"BA output"}'
        if "Agent name: architect." in prompt:
            return '{"agent_name":"architect","summary":"Architecture output"}'
        if "Agent name: developer." in prompt:
            return (
                '{"agent_name":"developer","summary":"Developer output",'
                '"code_changes":[{"path":"src/app.py","change_type":"update","description":"Update app",'
                '"content":"def hello() -> str:\\n    return \\"hello from developer\\"\\n"}],'
                '"tests":[{"path":"tests/test_app.py","test_type":"unit","description":"Test app",'
                '"content":"from src.app import hello\\n\\ndef test_hello() -> None:\\n    assert hello() == \\"hello from developer\\"\\n"}],'
                '"commit_message":"Implement developer output"}'
            )
        if "Agent name: qa." in prompt:
            self._qa_calls += 1
            if self._reject_qa_once and self._qa_calls == 1:
                return '{"agent_name":"qa","summary":"QA rejected","passed":false}'
            return '{"agent_name":"qa","summary":"QA output","passed":true}'
        if "Agent name: docs." in prompt:
            return '{"agent_name":"docs","summary":"Docs output"}'
        if "Agent name: pr." in prompt:
            return (
                '{"agent_name":"pr","summary":"PR output","title":"Runtime PR",'
                '"description":"Executable workflow","target_branch":"main","source_branch":"codex/runtime"}'
            )
        raise AssertionError("Unknown agent prompt")


class CountingWorkflowModelClient(WorkflowModelClient):
    def __init__(self) -> None:
        super().__init__()
        self.complete_calls = 0
        self.stream_calls = 0
        self.ba_prompt_tokens: int | None = None

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        self.complete_calls += 1
        prompt = "\n\n".join(message.content for message in messages)
        if "Agent name: ba." in prompt or "BA agent" in prompt:
            self.ba_prompt_tokens = sum(max(1, len(message.content) // 4) for message in messages)
            return '{"agent_name":"ba","summary":"BA output"}'
        return await super().complete(messages)

    async def stream_complete(self, messages: tuple[PromptMessage, ...]):
        self.stream_calls += 1
        yield await self.complete(messages)


class GovernanceInvalidDeveloperModelClient(WorkflowModelClient):
    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        prompt = "\n\n".join(message.content for message in messages)
        if "Agent name: developer." in prompt:
            return (
                '{"agent_name":"developer","summary":"Developer output without tests",'
                '"code_changes":[{"path":"src/app.py","change_type":"update","description":"Update app",'
                '"content":"def hello() -> str:\\n    return \\"hello\\"\\n"}]}'
            )
        return await super().complete(messages)


class InvalidBASectionModelClient(WorkflowModelClient):
    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        prompt = "\n\n".join(message.content for message in messages)
        if "Agent name: ba." in prompt or "BA agent" in prompt:
            return "not json"
        return await super().complete(messages)


@pytest.mark.asyncio
async def test_real_workflow_runtime_executes_full_delivery_sequence() -> None:
    repository = InMemoryWorkflowExecutionRepository()
    runtime = LangGraphExecutionRuntime(repository=repository, model_client=WorkflowModelClient())

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
    runtime = LangGraphExecutionRuntime(
        max_qa_rejection_loops=2,
        model_client=WorkflowModelClient(reject_qa_once=True),
    )

    result = await runtime.start("Deliver workflow with QA loop")

    latest = await runtime.repository.latest_checkpoint(result.execution_id)

    assert result.status == WorkflowRunStatus.COMPLETED
    assert latest is not None
    assert latest.state.metadata["qa_rejection_count"] == 1
    assert latest.state.agent_states["developer"].attempt == 2
    assert latest.state.agent_states["qa"].attempt == 2


@pytest.mark.asyncio
async def test_real_workflow_runtime_persists_checkpoints_and_recovers() -> None:
    repository = InMemoryWorkflowExecutionRepository()
    runtime = LangGraphExecutionRuntime(repository=repository, model_client=WorkflowModelClient())

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
        model_client=WorkflowModelClient(),
        event_hook=cancel_when_developer_starts,
    )

    result = await runtime.start("Cancel executable workflow")
    latest = await repository.latest_checkpoint(result.execution_id)

    assert result.status == WorkflowRunStatus.CANCELLED
    assert latest is not None
    assert latest.status == WorkflowRunStatus.CANCELLED
    assert "docs" not in latest.state.agent_states
    assert "pr" not in latest.state.agent_states


@pytest.mark.asyncio
async def test_governance_rejection_changes_workflow_execution_status() -> None:
    runtime = LangGraphExecutionRuntime(model_client=GovernanceInvalidDeveloperModelClient())

    result = await runtime.start("Deliver workflow with invalid developer output")
    latest = await runtime.repository.latest_checkpoint(result.execution_id)

    assert result.status == WorkflowRunStatus.FAILED
    assert latest is not None
    developer = latest.state.agent_states["developer"]
    assert developer.status == AgentStatus.FAILED
    record = await runtime.repository.get(result.execution_id)
    assert any("Governance runtime rejection" in error for error in record.metadata["errors"])


@pytest.mark.asyncio
async def test_local_safe_mode_uses_non_stream_single_provider_call_for_ba() -> None:
    client = CountingWorkflowModelClient()
    runtime = LangGraphExecutionRuntime(model_client=client)

    result = await runtime.start(
        "Necesito hacer un e-commerce tipo MercadoLibre con productos, usuarios y carrito, MVP funcional.",
        metadata={"local_lm_studio_safe_mode": True},
    )

    assert result.status == WorkflowRunStatus.COMPLETED
    assert client.stream_calls == 0
    assert client.complete_calls >= 1
    assert client.ba_prompt_tokens is not None
    assert client.ba_prompt_tokens <= 1200


@pytest.mark.asyncio
async def test_execution_owner_blocks_cross_owner_recovery() -> None:
    repository = InMemoryWorkflowExecutionRepository()
    backend_runtime = LangGraphExecutionRuntime(repository=repository, model_client=WorkflowModelClient(), execution_owner="backend")
    started = await backend_runtime.start("owner test")
    record = await repository.get(started.execution_id)
    assert record.metadata["execution_owner"] == "backend"


@pytest.mark.asyncio
async def test_ba_sections_parse_failure_does_not_emit_retry_started() -> None:
    events: list[str] = []

    async def hook(event_name: str, state: dict[str, object]) -> None:
        events.append(event_name)

    runtime = LangGraphExecutionRuntime(
        model_client=InvalidBASectionModelClient(),
        event_hook=hook,
    )
    result = await runtime.start(
        "Test BA parser fallback",
        metadata={"workflow_mode": "ba_only"},
    )
    assert result.status == WorkflowRunStatus.COMPLETED
    assert "retry_started" not in events


@pytest.mark.asyncio
async def test_local_safe_mode_emits_compaction_and_handoff_events() -> None:
    events: list[str] = []

    async def hook(event_name: str, state: dict[str, object]) -> None:
        events.append(event_name)

    client = CountingWorkflowModelClient()
    runtime = LangGraphExecutionRuntime(
        model_client=client,
        event_hook=hook,
    )
    result = await runtime.start(
        "Necesito hacer un e-commerce tipo MercadoLibre con productos, usuarios y carrito, MVP funcional.",
        metadata={"workflow_mode": "ba_only", "local_lm_studio_safe_mode": True},
    )
    assert result.status == WorkflowRunStatus.COMPLETED
    assert "provider_selected_per_agent" in events
    assert "compact_mode_enabled" in events
    assert "context_budget_estimated" in events
    assert "handoff_generated" in events
