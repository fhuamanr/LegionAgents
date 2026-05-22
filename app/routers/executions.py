"""Execution APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.schemas import ExecutionLogResponse, ExecutionStatusResponse, WorkflowTelemetryResponse
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{workflow_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionStatusResponse:
    return await service.get_execution_status(workflow_id)


@router.get("/{workflow_id}/logs", response_model=ExecutionLogResponse)
async def get_execution_logs(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionLogResponse:
    return await service.get_logs(workflow_id)


@router.get("/{workflow_id}/telemetry", response_model=WorkflowTelemetryResponse)
async def get_workflow_telemetry(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowTelemetryResponse:
    return await service.get_workflow_telemetry(workflow_id)
