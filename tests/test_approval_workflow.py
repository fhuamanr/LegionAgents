from uuid import uuid4

import pytest

from core.approvals import ApprovalGateEvaluator, ApprovalWorkflowService
from core.contracts.approvals import (
    ApprovalDecision,
    ApprovalDecisionRequest,
    ApprovalGateType,
    ApprovalRequest,
    ApprovalStatus,
    Reviewer,
    WorkflowPauseReason,
)
from core.contracts.states import WorkflowExecutionState


@pytest.mark.asyncio
async def test_approval_gate_pauses_and_resumes_workflow() -> None:
    service = ApprovalWorkflowService()
    workflow_id = uuid4()

    approval, pause = await service.create_gate(
        ApprovalRequest(
            workflow_id=workflow_id,
            gate_type=ApprovalGateType.QA_OVERRIDE,
            title="Approve QA override",
            description="Allow workflow to continue despite QA rejection.",
            requested_by="qa",
            required_reviewers=(Reviewer(reviewer_id="lead-1", display_name="Delivery Lead"),),
            pause_reason=WorkflowPauseReason.QA_OVERRIDE_REQUIRED,
        )
    )

    assert approval.status == ApprovalStatus.PENDING
    assert pause.approval_id == approval.id
    assert (await service.resume_decision(workflow_id)).can_resume is False

    decision = await service.decide(
        approval.id,
        ApprovalDecisionRequest(
            decision=ApprovalDecision.APPROVE,
            reviewer=Reviewer(reviewer_id="lead-1", display_name="Delivery Lead"),
            reason="Risk accepted for this delivery.",
        ),
    )

    assert decision.can_resume is True
    assert decision.route_signal == "qa_override_approved"
    assert await service.get_pause(workflow_id) is None


@pytest.mark.asyncio
async def test_rejected_approval_keeps_workflow_blocked() -> None:
    service = ApprovalWorkflowService()
    approval, _ = await service.create_gate(
        ApprovalRequest(
            workflow_id=uuid4(),
            gate_type=ApprovalGateType.PR_APPROVAL,
            title="Review PR",
            description="Approve PR draft.",
            requested_by="pr",
        )
    )

    decision = await service.decide(
        approval.id,
        ApprovalDecisionRequest(
            decision=ApprovalDecision.REJECT,
            reviewer=Reviewer(reviewer_id="reviewer-1", display_name="Reviewer"),
            reason="PR needs changes.",
        ),
    )

    assert decision.can_resume is False
    assert decision.route_signal == "reject"
    assert (await service.get(approval.id)).status == ApprovalStatus.REJECTED


@pytest.mark.asyncio
async def test_langgraph_approval_evaluator_marks_state_paused() -> None:
    service = ApprovalWorkflowService()
    evaluator = ApprovalGateEvaluator(service)
    state = WorkflowExecutionState(workflow_id=uuid4(), task="Deliver feature")

    paused = await evaluator.pause_for_approval(
        state,
        ApprovalRequest(
            workflow_id=state.workflow_id,
            gate_type=ApprovalGateType.RETRY_APPROVAL,
            title="Approve retry",
            description="Developer retry requires human approval.",
            requested_by="supervisor",
            pause_reason=WorkflowPauseReason.RETRY_REQUIRES_APPROVAL,
        ),
    )

    assert paused.metadata["paused"] is True
    assert paused.metadata["route_signal"] == "pause"
    assert "approval_id" in paused.metadata
