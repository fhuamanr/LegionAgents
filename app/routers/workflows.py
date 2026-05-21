"""Workflow APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.schemas import TriggerWorkflowRequest, WorkflowResponse
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=202)
async def trigger_workflow(
    request: TriggerWorkflowRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.trigger_workflow(request)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.get_workflow(workflow_id)

