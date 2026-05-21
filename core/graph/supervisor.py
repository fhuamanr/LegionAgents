"""Supervisor node for conditional workflow routing."""

from core.contracts.states import WorkflowExecutionState
from core.graph.routing import WorkflowRouter
from core.graph.state import LangGraphRuntimeState
from core.graph.transitions import append_workflow_transition


class SupervisorNode:
    """Routes workflow state without executing agent business logic."""

    def __init__(self, router: WorkflowRouter) -> None:
        self._router = router

    async def __call__(self, state: LangGraphRuntimeState) -> LangGraphRuntimeState:
        workflow_state = state["workflow_state"]
        decision = self._router.route(workflow_state)
        source = workflow_state.active_agent or "__start__"
        updated = workflow_state.model_copy(
            update={
                "metadata": append_workflow_transition(
                    metadata=workflow_state.metadata,
                    source=source,
                    decision=decision,
                )
            }
        )
        return {"workflow_state": updated}

    def route_key(self, state: LangGraphRuntimeState) -> str:
        """Return the conditional edge key for LangGraph."""

        return str(state["workflow_state"].metadata.get("next_agent", "__end__"))
