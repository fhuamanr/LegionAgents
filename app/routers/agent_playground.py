"""Agent playground and step runner APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.container import get_execution_service
from app.schemas import (
    AgentPlaygroundArtifactListResponse,
    AgentPlaygroundArtifactSummary,
    AgentPlaygroundHandoffUpdateRequest,
    AgentPlaygroundRunRequest,
    AgentPlaygroundRunResponse,
    AgentPlaygroundWorkflowRunRequest,
    WorkflowResponse,
)
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/agent-playground", tags=["agent-playground"])


@router.post("/run", response_model=AgentPlaygroundRunResponse)
async def run_agent_step(
    request: AgentPlaygroundRunRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> AgentPlaygroundRunResponse:
    try:
        return await service.run_agent_playground(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workflow_id}/artifacts", response_model=AgentPlaygroundArtifactListResponse)
async def list_step_artifacts(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> AgentPlaygroundArtifactListResponse:
    return await service.list_agent_playground_artifacts(workflow_id)


@router.put("/{workflow_id}/artifacts/{execution_id}/handoff", response_model=AgentPlaygroundArtifactSummary)
async def update_handoff(
    workflow_id: UUID,
    execution_id: UUID,
    request: AgentPlaygroundHandoffUpdateRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> AgentPlaygroundArtifactSummary:
    try:
        return await service.update_playground_handoff(workflow_id, execution_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found.") from exc


@router.post("/workflow/run", response_model=WorkflowResponse, status_code=202)
async def run_workflow_with_toggles(
    request: AgentPlaygroundWorkflowRunRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowResponse:
    return await service.trigger_workflow_with_toggles(request)
