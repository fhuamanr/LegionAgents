"""LangGraph orchestration base.

Business workflow behavior belongs in specialized agents. This module only
coordinates state transitions and delegates execution through agent boundaries.
"""

from abc import ABC, abstractmethod

from langgraph.graph.state import CompiledStateGraph

from core.contracts.execution import AgentExecutionResult
from core.contracts.states import WorkflowExecutionState
from core.contracts.workflow import WorkflowDefinition, WorkflowState
from core.graph.builder import LangGraphBuilder
from core.graph.nodes import AgentExecutor
from core.graph.routing import RoutingPolicy
from core.graph.state import LangGraphRuntimeState


class GraphOrchestrator(ABC):
    """Coordinates workflow execution without owning agent business logic."""

    @abstractmethod
    async def execute(self, state: WorkflowExecutionState) -> WorkflowExecutionState:
        """Execute a workflow and return the updated state."""


class LangGraphWorkflowAdapter(GraphOrchestrator):
    """LangGraph-backed workflow orchestrator."""

    def __init__(
        self,
        workflow: WorkflowDefinition,
        executors: dict[str, AgentExecutor],
        compiled_graph: CompiledStateGraph | None = None,
        routing_policy: RoutingPolicy | None = None,
    ) -> None:
        self._workflow = workflow
        self._executors = executors
        self._compiled_graph = compiled_graph
        self._routing_policy = routing_policy

    async def execute(self, state: WorkflowExecutionState) -> WorkflowExecutionState:
        runtime_state: LangGraphRuntimeState = {"workflow_state": state}
        result = await self._graph.ainvoke(runtime_state)
        return result["workflow_state"]

    async def execute_legacy(self, state: WorkflowState) -> WorkflowState:
        """Run the graph and return the original lightweight state shape."""

        execution_state = WorkflowExecutionState(
            workflow_id=state.workflow_id,
            task=state.task,
            active_agent=state.active_agent,
            artifacts=state.artifacts,
            metadata=state.metadata,
        )
        result = await self.execute(execution_state)
        return WorkflowState(
            workflow_id=result.workflow_id,
            task=result.task,
            active_agent=result.active_agent,
            statuses={
                agent_name: snapshot.status
                for agent_name, snapshot in result.agent_states.items()
            },
            results=self._legacy_results(result),
            artifacts=result.artifacts,
            metadata=result.metadata,
        )

    @property
    def _graph(self) -> CompiledStateGraph:
        if self._compiled_graph is None:
            self._compiled_graph = LangGraphBuilder(
                workflow=self._workflow,
                executors=self._executors,
                routing_policy=self._routing_policy,
            ).build()
        return self._compiled_graph

    def _legacy_results(
        self,
        state: WorkflowExecutionState,
    ) -> dict[str, AgentExecutionResult]:
        results: dict[str, AgentExecutionResult] = {}
        for agent_name, snapshot in state.agent_states.items():
            results[agent_name] = AgentExecutionResult(
                execution_id=state.workflow_id,
                agent_name=agent_name,
                status=snapshot.status,
                summary=str(snapshot.metadata.get("summary", "")),
                artifacts=snapshot.output_artifacts,
                errors=(snapshot.last_error,) if snapshot.last_error else tuple(),
                metadata=snapshot.metadata,
            )
        return results
