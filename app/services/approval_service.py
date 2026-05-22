"""Approval application service for FastAPI adapters."""

from uuid import UUID

from app.schemas import (
    ApprovalDecisionApiRequest,
    ApprovalListResponse,
    ApprovalResponse,
    CreateApprovalRequest,
    WorkflowPauseResponse,
    WorkflowResumeResponse,
)
from app.services.execution_service import ExecutionService
from core.approvals import ApprovalWorkflowService
from core.contracts.approvals import (
    ApprovalDecision,
    ApprovalDecisionRequest,
    ApprovalGateType,
    ApprovalQuery,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    Reviewer,
    WorkflowPause,
    WorkflowPauseReason,
    WorkflowResumeDecision,
)
from core.streaming import ExecutionEventType


class ApprovalApplicationService:
    """FastAPI-facing approval service."""

    def __init__(
        self,
        execution_service: ExecutionService,
        approval_service: ApprovalWorkflowService | None = None,
    ) -> None:
        self._execution_service = execution_service
        self._approval_service = approval_service or ApprovalWorkflowService()

    async def create_approval(self, request: CreateApprovalRequest) -> tuple[ApprovalResponse, WorkflowPauseResponse]:
        approval, pause = await self._approval_service.create_gate(
            ApprovalRequest(
                workflow_id=request.workflow_id,
                gate_type=ApprovalGateType(request.gate_type),
                title=request.title,
                description=request.description,
                requested_by=request.requested_by,
                required_reviewers=tuple(self._reviewer(reviewer) for reviewer in request.required_reviewers),
                agent_name=request.agent_name,
                thread_id=request.thread_id,
                pause_reason=WorkflowPauseReason(request.pause_reason),
                metadata=request.metadata,
            )
        )
        await self._execution_service.pause_workflow(
            request.workflow_id,
            {
                "paused": True,
                "approval_id": str(approval.id),
                "pause_reason": pause.reason.value,
                "approval_gate_type": approval.gate_type.value,
            },
        )
        await self._execution_service.emitter.emit(
            ExecutionEventType.PROGRESS_UPDATED,
            workflow_id=request.workflow_id,
            thread_id=request.thread_id,
            agent_name=request.agent_name,
            message=f"Workflow paused for approval: {approval.title}",
            payload={"approval_id": str(approval.id), "gate_type": approval.gate_type.value},
        )
        return self._approval_response(approval), self._pause_response(pause)

    async def decide(self, approval_id: UUID, request: ApprovalDecisionApiRequest) -> WorkflowResumeResponse:
        decision = await self._approval_service.decide(
            approval_id,
            ApprovalDecisionRequest(
                decision=ApprovalDecision(request.decision),
                reviewer=self._reviewer(request.reviewer),
                reason=request.reason,
                metadata=request.metadata,
            ),
        )
        if decision.can_resume:
            await self._execution_service.resume_workflow(
                decision.workflow_id,
                {
                    "paused": False,
                    "approval_id": str(decision.approval_id),
                    "approval_route_signal": decision.route_signal,
                    "approval_resume_reason": decision.reason,
                },
            )
            await self._execution_service.emitter.emit(
                ExecutionEventType.PROGRESS_UPDATED,
                workflow_id=decision.workflow_id,
                message="Workflow approval accepted; execution can resume.",
                payload=decision.model_dump(mode="json"),
            )
        return self._resume_response(decision)

    async def list_approvals(
        self,
        workflow_id: UUID | None = None,
        status: str | None = None,
        gate_type: str | None = None,
    ) -> ApprovalListResponse:
        query = ApprovalQuery(
            workflow_id=workflow_id,
            status=ApprovalStatus(status) if status else None,
            gate_type=ApprovalGateType(gate_type) if gate_type else None,
        )
        approvals = await self._approval_service.list(query)
        return ApprovalListResponse(approvals=tuple(self._approval_response(approval) for approval in approvals))

    async def get_approval(self, approval_id: UUID) -> ApprovalResponse:
        return self._approval_response(await self._approval_service.get(approval_id))

    async def get_pause(self, workflow_id: UUID) -> WorkflowPauseResponse | None:
        pause = await self._approval_service.get_pause(workflow_id)
        return self._pause_response(pause) if pause else None

    async def resume_status(self, workflow_id: UUID) -> WorkflowResumeResponse:
        return self._resume_response(await self._approval_service.resume_decision(workflow_id))

    def _reviewer(self, reviewer) -> Reviewer:  # type: ignore[no-untyped-def]
        return Reviewer(
            reviewer_id=reviewer.reviewer_id,
            display_name=reviewer.display_name,
            email=reviewer.email,
            role=reviewer.role,
        )

    def _approval_response(self, approval: ApprovalRecord) -> ApprovalResponse:
        return ApprovalResponse(
            approval_id=approval.id,
            workflow_id=approval.workflow_id,
            gate_type=approval.gate_type.value,
            status=approval.status.value,
            title=approval.title,
            description=approval.description,
            requested_by=approval.requested_by,
            required_reviewers=tuple(reviewer.model_dump(mode="json") for reviewer in approval.required_reviewers),
            agent_name=approval.agent_name,
            thread_id=approval.thread_id,
            pause_reason=approval.pause_reason.value,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
            decided_at=approval.decided_at,
            decided_by=approval.decided_by.model_dump(mode="json") if approval.decided_by else None,
            decision_reason=approval.decision_reason,
            metadata=approval.metadata,
        )

    def _pause_response(self, pause: WorkflowPause) -> WorkflowPauseResponse:
        return WorkflowPauseResponse(
            workflow_id=pause.workflow_id,
            approval_id=pause.approval_id,
            reason=pause.reason.value,
            paused_at=pause.paused_at,
            resume_token=pause.resume_token,
            metadata=pause.metadata,
        )

    def _resume_response(self, decision: WorkflowResumeDecision) -> WorkflowResumeResponse:
        return WorkflowResumeResponse(
            workflow_id=decision.workflow_id,
            approval_id=decision.approval_id,
            can_resume=decision.can_resume,
            route_signal=decision.route_signal,
            reason=decision.reason,
            metadata=decision.metadata,
        )
