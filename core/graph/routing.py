"""Routing infrastructure for LangGraph workflows."""

from dataclasses import dataclass, field
from enum import StrEnum

from langgraph.graph import END

from core.contracts.agents import AgentStatus
from core.contracts.states import AgentStateSnapshot, WorkflowExecutionState
from core.contracts.workflow import WorkflowDefinition


class RouteSignal(StrEnum):
    """Generic route signals emitted as execution metadata by agents."""

    CONTINUE = "continue"
    RETRY = "retry"
    REJECT = "reject"
    COMPLETE = "complete"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    """Routing limits and role names for workflow infrastructure."""

    max_agent_attempts: int = 2
    max_rejection_loops: int = 2
    rejection_routes: dict[str, str] = field(default_factory=lambda: {"qa": "developer"})


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Decision produced by the workflow router."""

    target: str
    signal: RouteSignal
    reason: str


class WorkflowRouter:
    """Computes the next graph target from minimal workflow state."""

    def __init__(
        self,
        workflow: WorkflowDefinition,
        executable_agents: tuple[str, ...],
        policy: RoutingPolicy | None = None,
    ) -> None:
        self._workflow = workflow
        self._executable_agents = executable_agents
        self._policy = policy or RoutingPolicy()

    def route(self, state: WorkflowExecutionState) -> RouteDecision:
        if not self._executable_agents:
            return RouteDecision(target=END, signal=RouteSignal.COMPLETE, reason="no_executable_agents")

        active_agent = state.active_agent
        if active_agent is None:
            return RouteDecision(
                target=self._executable_agents[0],
                signal=RouteSignal.CONTINUE,
                reason="workflow_started",
            )

        snapshot = state.agent_states.get(active_agent)
        if snapshot is None:
            return self._next_after(active_agent, RouteSignal.CONTINUE, "missing_agent_snapshot")

        signal = self._signal(snapshot)
        if signal == RouteSignal.COMPLETE:
            return RouteDecision(target=END, signal=signal, reason="agent_requested_completion")
        if signal == RouteSignal.FAIL:
            return RouteDecision(target=END, signal=signal, reason="agent_requested_failure")
        if signal == RouteSignal.RETRY or snapshot.status == AgentStatus.FAILED:
            return self._retry_or_end(snapshot)
        if signal == RouteSignal.REJECT:
            return self._rejection_or_continue(state, snapshot)

        return self._next_after(active_agent, RouteSignal.CONTINUE, "default_sequence")

    def route_key(self, state: WorkflowExecutionState) -> str:
        """Return the raw LangGraph conditional edge target."""

        return self.route(state).target

    def _next_after(
        self,
        agent_name: str,
        signal: RouteSignal,
        reason: str,
    ) -> RouteDecision:
        try:
            current_index = self._executable_agents.index(agent_name)
        except ValueError:
            return RouteDecision(target=END, signal=RouteSignal.FAIL, reason="unknown_active_agent")

        next_index = current_index + 1
        if next_index >= len(self._executable_agents):
            return RouteDecision(target=END, signal=RouteSignal.COMPLETE, reason="workflow_completed")
        return RouteDecision(
            target=self._executable_agents[next_index],
            signal=signal,
            reason=reason,
        )

    def _retry_or_end(self, snapshot: AgentStateSnapshot) -> RouteDecision:
        if snapshot.attempt < self._policy.max_agent_attempts:
            return RouteDecision(
                target=snapshot.agent_name,
                signal=RouteSignal.RETRY,
                reason="retry_attempt_available",
            )
        return RouteDecision(target=END, signal=RouteSignal.FAIL, reason="retry_limit_reached")

    def _rejection_or_continue(
        self,
        state: WorkflowExecutionState,
        snapshot: AgentStateSnapshot,
    ) -> RouteDecision:
        target = self._policy.rejection_routes.get(snapshot.agent_name)
        if target is None or target not in self._executable_agents:
            return self._next_after(snapshot.agent_name, RouteSignal.CONTINUE, "no_rejection_route")

        rejection_count = int(state.metadata.get(f"{snapshot.agent_name}_rejection_count", 0))
        if rejection_count >= self._policy.max_rejection_loops:
            return RouteDecision(target=END, signal=RouteSignal.FAIL, reason="rejection_loop_limit_reached")
        return RouteDecision(target=target, signal=RouteSignal.REJECT, reason="rejection_route")

    def _signal(self, snapshot: AgentStateSnapshot) -> RouteSignal:
        raw_signal = snapshot.metadata.get("route_signal") or snapshot.metadata.get("route")
        if raw_signal is None:
            return RouteSignal.CONTINUE
        try:
            return RouteSignal(str(raw_signal))
        except ValueError:
            return RouteSignal.CONTINUE

