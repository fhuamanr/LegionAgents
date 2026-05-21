"""LangGraph runtime state adapters."""

from typing import TypedDict

from core.contracts.states import WorkflowExecutionState


class LangGraphRuntimeState(TypedDict):
    """State shape exchanged between LangGraph nodes.

    The Pydantic workflow state remains the platform contract. This TypedDict
    is only the adapter shape LangGraph uses while executing nodes.
    """

    workflow_state: WorkflowExecutionState

