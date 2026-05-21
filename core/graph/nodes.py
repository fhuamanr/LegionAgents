"""LangGraph node primitives."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.states import (
    AgentPhase,
    AgentStateSnapshot,
    AgentTransition,
    WorkflowExecutionState,
)
from core.graph.state import LangGraphRuntimeState


class AgentExecutor(ABC):
    """Execution boundary for one specialized agent."""

    @abstractmethod
    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        """Run a single agent and return its structured execution result."""


class GraphNode(ABC):
    """Base callable node for LangGraph orchestration."""

    @abstractmethod
    async def __call__(self, state: LangGraphRuntimeState) -> LangGraphRuntimeState:
        """Execute the node and return state updates."""


class AgentGraphNode(GraphNode):
    """LangGraph node that delegates to a specialized agent executor."""

    def __init__(self, agent_name: str, executor: AgentExecutor) -> None:
        self._agent_name = agent_name
        self._executor = executor

    async def __call__(self, state: LangGraphRuntimeState) -> LangGraphRuntimeState:
        workflow_state = state["workflow_state"]
        started_at = datetime.now(timezone.utc)
        running_state = self._mark_running(workflow_state, started_at)

        request = AgentExecutionRequest(
            workflow_id=running_state.workflow_id,
            agent_name=self._agent_name,
            task=running_state.task,
            upstream_artifacts=running_state.artifacts,
        )

        try:
            result = await self._executor.execute(request)
        except Exception as exc:
            failed_state = self._mark_failed(running_state, str(exc))
            return {"workflow_state": failed_state}

        completed_state = self._apply_result(running_state, result)
        return {"workflow_state": completed_state}

    def _mark_running(
        self,
        workflow_state: WorkflowExecutionState,
        started_at: datetime,
    ) -> WorkflowExecutionState:
        previous = workflow_state.agent_states.get(self._agent_name)
        snapshot = AgentStateSnapshot(
            agent_name=self._agent_name,
            status=AgentStatus.RUNNING,
            phase=AgentPhase.EXECUTING,
            attempt=(previous.attempt + 1 if previous else 1),
            started_at=started_at,
            input_artifacts=workflow_state.artifacts,
        )
        transition = AgentTransition(
            agent_name=self._agent_name,
            from_phase=previous.phase if previous else AgentPhase.CREATED,
            to_phase=AgentPhase.EXECUTING,
            reason="agent_execution_started",
        )
        return workflow_state.model_copy(
            update={
                "active_agent": self._agent_name,
                "agent_states": {
                    **workflow_state.agent_states,
                    self._agent_name: snapshot,
                },
                "transitions": workflow_state.transitions + (transition,),
            }
        )

    def _apply_result(
        self,
        workflow_state: WorkflowExecutionState,
        result: AgentExecutionResult,
    ) -> WorkflowExecutionState:
        completed_at = datetime.now(timezone.utc)
        phase = (
            AgentPhase.COMPLETED
            if result.status == AgentStatus.COMPLETED
            else AgentPhase.FAILED
        )
        previous = workflow_state.agent_states[self._agent_name]
        snapshot = previous.model_copy(
            update={
                "status": result.status,
                "phase": phase,
                "completed_at": completed_at,
                "last_error": "; ".join(result.errors) if result.errors else None,
                "output_artifacts": result.artifacts,
                "metadata": {**previous.metadata, **result.metadata, "summary": result.summary},
            }
        )
        transition = AgentTransition(
            agent_name=self._agent_name,
            from_phase=AgentPhase.EXECUTING,
            to_phase=phase,
            reason="agent_execution_finished",
        )
        return workflow_state.model_copy(
            update={
                "agent_states": {
                    **workflow_state.agent_states,
                    self._agent_name: snapshot,
                },
                "transitions": workflow_state.transitions + (transition,),
                "artifacts": workflow_state.artifacts + result.artifacts,
                "metadata": self._update_workflow_metadata_for_result(
                    workflow_state.metadata,
                    result,
                ),
            }
        )

    def _mark_failed(
        self,
        workflow_state: WorkflowExecutionState,
        error: str,
    ) -> WorkflowExecutionState:
        completed_at = datetime.now(timezone.utc)
        previous = workflow_state.agent_states[self._agent_name]
        snapshot = previous.model_copy(
            update={
                "status": AgentStatus.FAILED,
                "phase": AgentPhase.FAILED,
                "completed_at": completed_at,
                "last_error": error,
            }
        )
        transition = AgentTransition(
            agent_name=self._agent_name,
            from_phase=AgentPhase.EXECUTING,
            to_phase=AgentPhase.FAILED,
            reason="agent_execution_failed",
            metadata={"error": error},
        )
        return workflow_state.model_copy(
            update={
                "agent_states": {
                    **workflow_state.agent_states,
                    self._agent_name: snapshot,
                },
                "transitions": workflow_state.transitions + (transition,),
            }
        )

    def _update_workflow_metadata_for_result(
        self,
        metadata: dict[str, object],
        result: AgentExecutionResult,
    ) -> dict[str, object]:
        route_signal = result.metadata.get("route_signal") or result.metadata.get("route")
        if route_signal != "reject":
            return metadata
        key = f"{self._agent_name}_rejection_count"
        return {**metadata, key: int(metadata.get(key, 0)) + 1}
