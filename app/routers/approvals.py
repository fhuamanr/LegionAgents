"""Human approval workflow APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.container import get_approval_service
from app.schemas import (
    ApprovalDecisionApiRequest,
    ApprovalListResponse,
    ApprovalResponse,
    CreateApprovalRequest,
    WorkflowPauseResponse,
    WorkflowResumeResponse,
)
from app.services.approval_service import ApprovalApplicationService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=ApprovalResponse, status_code=201)
async def create_approval(
    request: CreateApprovalRequest,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> ApprovalResponse:
    approval, _ = await service.create_approval(request)
    return approval


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    workflow_id: UUID | None = None,
    status: str | None = None,
    gate_type: str | None = None,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> ApprovalListResponse:
    return await service.list_approvals(workflow_id=workflow_id, status=status, gate_type=gate_type)


@router.get("/workflows/{workflow_id}/pause", response_model=WorkflowPauseResponse)
async def get_workflow_pause(
    workflow_id: UUID,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> WorkflowPauseResponse:
    pause = await service.get_pause(workflow_id)
    if pause is None:
        raise HTTPException(status_code=404, detail="Workflow is not paused.")
    return pause


@router.get("/workflows/{workflow_id}/resume", response_model=WorkflowResumeResponse)
async def get_workflow_resume_status(
    workflow_id: UUID,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> WorkflowResumeResponse:
    return await service.resume_status(workflow_id)


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> ApprovalResponse:
    return await service.get_approval(approval_id)


@router.post("/{approval_id}/decisions", response_model=WorkflowResumeResponse)
async def decide_approval(
    approval_id: UUID,
    request: ApprovalDecisionApiRequest,
    service: ApprovalApplicationService = Depends(get_approval_service),
) -> WorkflowResumeResponse:
    return await service.decide(approval_id, request)
