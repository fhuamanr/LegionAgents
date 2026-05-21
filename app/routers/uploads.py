"""Upload APIs."""

from fastapi import APIRouter, Depends

from app.dependencies.container import get_execution_service
from app.schemas import UploadResponse, UserStoryUploadRequest
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/user-stories", response_model=UploadResponse, status_code=201)
async def upload_user_story(
    request: UserStoryUploadRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> UploadResponse:
    return await service.upload_user_story(request)

