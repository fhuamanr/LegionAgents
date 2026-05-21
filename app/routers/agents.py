"""Agent status APIs."""

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.schemas import AgentStatusResponse
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_statuses(
    service: ExecutionService = Depends(get_execution_service),
) -> AgentStatusResponse:
    return AgentStatusResponse(agents=await service.get_agent_statuses())

