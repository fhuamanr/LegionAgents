"""Workflow APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import HTTPException

from app.dependencies.container import get_execution_service
from app.schemas import (
    ImproveExecutionRequest,
    ImproveExecutionResponse,
    TriggerWorkflowRequest,
    WorkflowArtifactFile,
    WorkflowArtifactListResponse,
    WorkflowResponse,
)
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=202)
async def trigger_workflow(
    request: TriggerWorkflowRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.trigger_workflow(request)


@router.post("/live", response_model=WorkflowResponse, status_code=202)
async def trigger_live_workflow(
    request: TriggerWorkflowRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.trigger_workflow_live(request)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.get_workflow(workflow_id)


@router.get("/{workflow_id}/artifacts", response_model=WorkflowArtifactListResponse)
async def list_workflow_artifacts(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowArtifactListResponse:
    return await service.list_workflow_artifacts(workflow_id)


@router.get("/{workflow_id}/artifacts/{agent_name}", response_model=WorkflowArtifactListResponse)
async def list_workflow_agent_artifacts(
    workflow_id: UUID,
    agent_name: str,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowArtifactListResponse:
    return await service.list_workflow_artifacts(workflow_id, agent_name=agent_name)


@router.get("/{workflow_id}/artifacts/{agent_name}/{artifact_name:path}", response_model=WorkflowArtifactFile)
async def read_workflow_agent_artifact(
    workflow_id: UUID,
    agent_name: str,
    artifact_name: str,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowArtifactFile:
    try:
        return await service.read_workflow_artifact(workflow_id, agent_name, artifact_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found.") from exc


@router.post("/{workflow_id}/improve", response_model=ImproveExecutionResponse)
async def improve_existing_execution(
    workflow_id: UUID,
    request: ImproveExecutionRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> ImproveExecutionResponse:
    return await service.improve_existing_execution(workflow_id, request)

