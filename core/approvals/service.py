"""Human approval workflow service."""

from datetime import datetime, timezone
from uuid import UUID

from core.approvals.repository import ApprovalRepository, InMemoryApprovalRepository
from core.contracts.approvals import (
    ApprovalDecision,
    ApprovalDecisionRequest,
    ApprovalQuery,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    WorkflowPause,
    WorkflowResumeDecision,
)


class ApprovalWorkflowService:
    """Coordinates approval gates, workflow pauses, and resume decisions."""

    def __init__(self, repository: ApprovalRepository | None = None) -> None:
        self._repository = repository or InMemoryApprovalRepository()

    async def create_gate(self, request: ApprovalRequest) -> tuple[ApprovalRecord, WorkflowPause]:
        """Create an approval gate and pause its workflow."""

        approval = await self._repository.save(
            ApprovalRecord(
                workflow_id=request.workflow_id,
                gate_type=request.gate_type,
                title=request.title,
                description=request.description,
                requested_by=request.requested_by,
                required_reviewers=request.required_reviewers,
                agent_name=request.agent_name,
                thread_id=request.thread_id,
                pause_reason=request.pause_reason,
                metadata=request.metadata,
            )
        )
        pause = await self._repository.save_pause(
            WorkflowPause(
                workflow_id=request.workflow_id,
                approval_id=approval.id,
                reason=request.pause_reason,
                metadata={
                    "gate_type": request.gate_type.value,
                    "agent_name": request.agent_name,
                    "approval_status": approval.status.value,
                },
            )
        )
        return approval, pause

    async def decide(self, approval_id: UUID, request: ApprovalDecisionRequest) -> WorkflowResumeDecision:
        """Record a reviewer decision and return workflow resume metadata."""

        approval = await self._repository.get(approval_id)
        if approval.status != ApprovalStatus.PENDING:
            return WorkflowResumeDecision(
                workflow_id=approval.workflow_id,
                approval_id=approval.id,
                can_resume=False,
                route_signal="blocked",
                reason=f"Approval is already {approval.status.value}.",
                metadata={"approval_status": approval.status.value},
            )

        status = self._status_for_decision(request.decision)
        decided = approval.model_copy(
            update={
                "status": status,
                "decided_at": datetime.now(timezone.utc),
                "decided_by": request.reviewer,
                "decision_reason": request.reason,
                "metadata": {**approval.metadata, **request.metadata},
            }
        )
        await self._repository.save(decided)

        if status == ApprovalStatus.APPROVED:
            await self._repository.clear_pause(approval.workflow_id)
            return WorkflowResumeDecision(
                workflow_id=approval.workflow_id,
                approval_id=approval.id,
                can_resume=True,
                route_signal=self._approved_route_signal(approval),
                reason=request.reason,
                metadata={
                    "approval_status": status.value,
                    "reviewer_id": request.reviewer.reviewer_id,
                    "gate_type": approval.gate_type.value,
                },
            )

        return WorkflowResumeDecision(
            workflow_id=approval.workflow_id,
            approval_id=approval.id,
            can_resume=False,
            route_signal="reject",
            reason=request.reason,
            metadata={
                "approval_status": status.value,
                "reviewer_id": request.reviewer.reviewer_id,
                "gate_type": approval.gate_type.value,
            },
        )

    async def get(self, approval_id: UUID) -> ApprovalRecord:
        """Get an approval record."""

        return await self._repository.get(approval_id)

    async def list(self, query: ApprovalQuery | None = None) -> tuple[ApprovalRecord, ...]:
        """List approval records."""

        return await self._repository.list(query)

    async def get_pause(self, workflow_id: UUID) -> WorkflowPause | None:
        """Get active workflow pause state."""

        return await self._repository.get_pause(workflow_id)

    async def resume_decision(self, workflow_id: UUID) -> WorkflowResumeDecision:
        """Return whether a workflow can resume."""

        pause = await self._repository.get_pause(workflow_id)
        if pause is None:
            return WorkflowResumeDecision(
                workflow_id=workflow_id,
                approval_id=UUID(int=0),
                can_resume=True,
                route_signal="continue",
                reason="No active workflow pause.",
            )
        approval = await self._repository.get(pause.approval_id)
        return WorkflowResumeDecision(
            workflow_id=workflow_id,
            approval_id=approval.id,
            can_resume=False,
            route_signal="pause",
            reason=f"Workflow is paused awaiting {approval.gate_type.value}.",
            metadata={"approval_status": approval.status.value, "pause_reason": pause.reason.value},
        )

    def _status_for_decision(self, decision: ApprovalDecision) -> ApprovalStatus:
        if decision == ApprovalDecision.APPROVE:
            return ApprovalStatus.APPROVED
        if decision == ApprovalDecision.CANCEL:
            return ApprovalStatus.CANCELLED
        return ApprovalStatus.REJECTED

    def _approved_route_signal(self, approval: ApprovalRecord) -> str:
        if approval.gate_type.value == "qa_override":
            return "qa_override_approved"
        if approval.gate_type.value == "retry_approval":
            return "retry"
        if approval.gate_type.value == "pr_approval":
            return "continue_to_pr"
        return "continue"
