"""Prompt Engineering Studio APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.container import get_prompt_studio_service
from app.schemas import (
    PromptComparisonResponse,
    PromptListResponse,
    PromptPreviewApiRequest,
    PromptPreviewResponse,
    PromptResponse,
    PromptRollbackApiRequest,
    PromptTestApiRequest,
    PromptTestResponse,
    PromptUpsertApiRequest,
    PromptVersionListResponse,
)
from app.services.prompt_studio_service import PromptStudioApplicationService

router = APIRouter(prefix="/prompt-studio/prompts", tags=["prompt-studio"])


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    scope: str | None = None,
    agent_name: str | None = None,
    status: str | None = None,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptListResponse:
    return await service.list(scope=scope, agent_name=agent_name, status=status)


@router.post("", response_model=PromptResponse, status_code=201)
async def save_prompt(
    request: PromptUpsertApiRequest,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptResponse:
    return await service.save(request)


@router.post("/preview", response_model=PromptPreviewResponse)
async def preview_prompt(
    request: PromptPreviewApiRequest,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptPreviewResponse:
    return await service.preview(request)


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(
    request: PromptTestApiRequest,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptTestResponse:
    return await service.test(request)


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: UUID,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptResponse:
    return await service.get(prompt_id)


@router.get("/{prompt_id}/versions", response_model=PromptVersionListResponse)
async def get_prompt_versions(
    prompt_id: UUID,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptVersionListResponse:
    return await service.versions(prompt_id)


@router.post("/{prompt_id}/rollback", response_model=PromptResponse)
async def rollback_prompt(
    prompt_id: UUID,
    request: PromptRollbackApiRequest,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptResponse:
    return await service.rollback(prompt_id, request)


@router.get("/{prompt_id}/compare", response_model=PromptComparisonResponse)
async def compare_prompt_versions(
    prompt_id: UUID,
    left_version: int,
    right_version: int,
    service: PromptStudioApplicationService = Depends(get_prompt_studio_service),
) -> PromptComparisonResponse:
    return await service.compare(prompt_id, left_version, right_version)
