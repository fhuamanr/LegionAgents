from uuid import UUID

import pytest

from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact, ArtifactKind
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.states import AgentPhase, WorkflowExecutionState
from core.contracts.workflow import WorkflowDefinition, WorkflowState
from core.graph import AgentExecutor, LangGraphWorkflowAdapter, RoutingPolicy


class FakeAgentExecutor(AgentExecutor):
    def __init__(self, agent_name: str, calls: list[str]) -> None:
        self._agent_name = agent_name
        self._calls = calls

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        self._calls.append(request.agent_name)
        artifact = Artifact(
            id=f"{request.agent_name}-artifact",
            kind=ArtifactKind.GENERIC,
            name=f"{request.agent_name} output",
            producer_agent=request.agent_name,
            content=f"output from {request.agent_name}",
        )
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_name=self._agent_name,
            status=AgentStatus.COMPLETED,
            summary=f"{request.agent_name} completed",
            artifacts=(artifact,),
        )


class SequencedAgentExecutor(AgentExecutor):
    def __init__(
        self,
        agent_name: str,
        calls: list[str],
        results: list[AgentExecutionResult],
    ) -> None:
        self._agent_name = agent_name
        self._calls = calls
        self._results = results

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        self._calls.append(request.agent_name)
        if len(self._results) == 1:
            result = self._results[0]
        else:
            result = self._results.pop(0)
        return result.model_copy(
            update={
                "execution_id": request.execution_id,
                "agent_name": self._agent_name,
            }
        )


@pytest.mark.asyncio
async def test_langgraph_orchestrator_executes_agents_in_workflow_order() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("ba", "architect"))
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={
            "ba": FakeAgentExecutor("ba", calls),
            "architect": FakeAgentExecutor("architect", calls),
        },
    )

    result = await orchestrator.execute(WorkflowExecutionState(task="Build foundation"))

    assert calls == ["ba", "architect"]
    assert result.active_agent == "architect"
    assert result.agent_states["ba"].status == AgentStatus.COMPLETED
    assert result.agent_states["architect"].phase == AgentPhase.COMPLETED
    assert [artifact.producer_agent for artifact in result.artifacts] == ["ba", "architect"]


@pytest.mark.asyncio
async def test_langgraph_orchestrator_skips_agents_without_executor() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("ba", "qa"))
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={"qa": FakeAgentExecutor("qa", calls)},
    )

    result = await orchestrator.execute(WorkflowExecutionState(task="Build foundation"))

    assert calls == ["qa"]
    assert "ba" not in result.agent_states
    assert result.agent_states["qa"].status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_langgraph_orchestrator_legacy_adapter_returns_workflow_state() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("ba",))
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={"ba": FakeAgentExecutor("ba", calls)},
    )

    result = await orchestrator.execute_legacy(WorkflowState(task="Build foundation"))

    assert isinstance(result.workflow_id, UUID)
    assert result.statuses["ba"] == AgentStatus.COMPLETED
    assert result.results["ba"].summary == "ba completed"


@pytest.mark.asyncio
async def test_langgraph_orchestrator_retries_failed_agent_before_continuing() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("developer", "qa"))
    developer_results = [
        AgentExecutionResult(
            execution_id=UUID(int=0),
            agent_name="developer",
            status=AgentStatus.FAILED,
            errors=("temporary",),
            metadata={"route_signal": "retry"},
        ),
        AgentExecutionResult(
            execution_id=UUID(int=0),
            agent_name="developer",
            status=AgentStatus.COMPLETED,
            summary="developer recovered",
        ),
    ]
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={
            "developer": SequencedAgentExecutor("developer", calls, developer_results),
            "qa": FakeAgentExecutor("qa", calls),
        },
        routing_policy=RoutingPolicy(max_agent_attempts=2),
    )

    result = await orchestrator.execute(WorkflowExecutionState(task="Retry developer"))

    assert calls == ["developer", "developer", "qa"]
    assert result.agent_states["developer"].attempt == 2
    assert result.agent_states["developer"].status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_langgraph_orchestrator_supports_qa_rejection_loop_to_developer() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("developer", "qa", "docs", "pr"))
    qa_results = [
        AgentExecutionResult(
            execution_id=UUID(int=0),
            agent_name="qa",
            status=AgentStatus.COMPLETED,
            summary="qa rejected",
            metadata={"route_signal": "reject"},
        ),
        AgentExecutionResult(
            execution_id=UUID(int=0),
            agent_name="qa",
            status=AgentStatus.COMPLETED,
            summary="qa accepted",
        ),
    ]
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={
            "developer": FakeAgentExecutor("developer", calls),
            "qa": SequencedAgentExecutor("qa", calls, qa_results),
            "docs": FakeAgentExecutor("docs", calls),
            "pr": FakeAgentExecutor("pr", calls),
        },
        routing_policy=RoutingPolicy(max_rejection_loops=2),
    )

    result = await orchestrator.execute(WorkflowExecutionState(task="QA loop"))

    assert calls == ["developer", "qa", "developer", "qa", "docs", "pr"]
    assert result.metadata["qa_rejection_count"] == 1
    assert result.agent_states["developer"].attempt == 2
    assert result.agent_states["qa"].attempt == 2


@pytest.mark.asyncio
async def test_langgraph_orchestrator_records_workflow_transitions() -> None:
    calls: list[str] = []
    workflow = WorkflowDefinition(name="test", agents=("ba", "architect"))
    orchestrator = LangGraphWorkflowAdapter(
        workflow=workflow,
        executors={
            "ba": FakeAgentExecutor("ba", calls),
            "architect": FakeAgentExecutor("architect", calls),
        },
    )

    result = await orchestrator.execute(WorkflowExecutionState(task="Track transitions"))

    transitions = result.metadata["workflow_transitions"]
    assert transitions[0]["source"] == "__start__"
    assert transitions[0]["target"] == "ba"
    assert transitions[-1]["target"] == "__end__"
