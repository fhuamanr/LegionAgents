"""LangGraph approval gate integration helpers."""

from core.approvals.service import ApprovalWorkflowService
from core.contracts.approvals import ApprovalRequest
from core.contracts.states import WorkflowExecutionState


class ApprovalGateEvaluator:
    """Applies approval pause/resume metadata to LangGraph workflow state."""

    def __init__(self, approval_service: ApprovalWorkflowService) -> None:
        self._approval_service = approval_service

    async def pause_for_approval(
        self,
        state: WorkflowExecutionState,
        request: ApprovalRequest,
    ) -> WorkflowExecutionState:
        """Create an approval gate and annotate workflow state as paused."""

        approval, pause = await self._approval_service.create_gate(request)
        return state.model_copy(
            update={
                "metadata": {
                    **state.metadata,
                    "paused": True,
                    "pause_reason": pause.reason.value,
                    "approval_id": str(approval.id),
                    "resume_token": str(pause.resume_token),
                    "route_signal": "pause",
                }
            }
        )

    async def apply_resume_state(self, state: WorkflowExecutionState) -> WorkflowExecutionState:
        """Apply resume decision metadata for a LangGraph state."""

        decision = await self._approval_service.resume_decision(state.workflow_id)
        return state.model_copy(
            update={
                "metadata": {
                    **state.metadata,
                    "paused": not decision.can_resume,
                    "approval_id": str(decision.approval_id),
                    "route_signal": decision.route_signal,
                    "approval_resume_reason": decision.reason,
                }
            }
        )
