"""Workflow transition helpers."""

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from core.contracts.base import MutableContractBaseModel
from core.graph.routing import RouteDecision


class WorkflowTransition(MutableContractBaseModel):
    """Workflow-level transition metadata."""

    source: str
    target: str
    signal: str
    reason: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


def append_workflow_transition(
    metadata: dict[str, Any],
    source: str,
    decision: RouteDecision,
) -> dict[str, Any]:
    """Append a workflow transition to state metadata."""

    transition = WorkflowTransition(
        source=source,
        target=decision.target,
        signal=decision.signal.value,
        reason=decision.reason,
    )
    transitions = tuple(metadata.get("workflow_transitions", tuple()))
    return {
        **metadata,
        "next_agent": decision.target,
        "last_route_signal": decision.signal.value,
        "last_route_reason": decision.reason,
        "workflow_transitions": transitions + (transition.model_dump(mode="json"),),
    }

