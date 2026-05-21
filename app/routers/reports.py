"""Report retrieval APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.schemas import ReportResponse
from app.services.execution_service import ExecutionService

router = APIRouter(tags=["reports"])


@router.get("/reports/qa/{workflow_id}", response_model=ReportResponse)
async def get_qa_report(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> ReportResponse:
    return await service.get_report(workflow_id, "qa_report")


@router.get("/docs/generated/{workflow_id}", response_model=ReportResponse)
async def get_generated_documentation(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> ReportResponse:
    return await service.get_report(workflow_id, "generated_documentation")


@router.get("/pr/summaries/{workflow_id}", response_model=ReportResponse)
async def get_pr_summary(
    workflow_id: UUID,
    service: ExecutionService = Depends(get_execution_service),
) -> ReportResponse:
    return await service.get_report(workflow_id, "pr_summary")

