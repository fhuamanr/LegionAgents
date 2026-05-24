"""LLM provider management APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.container import get_provider_service
from app.schemas import ProviderConnectivityApiRequest, ProviderConnectivityResponse, ProviderHealthResponse, ProviderListResponse, ProviderModelProfileUpdateRequest, ProviderModelProfilesResponse, ProviderResponse, ProviderUpsertApiRequest
from app.services.provider_service import ProviderApplicationService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=ProviderListResponse)
async def list_providers(
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderListResponse:
    return await service.list()


@router.post("", response_model=ProviderResponse, status_code=201)
async def save_provider(
    request: ProviderUpsertApiRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderResponse:
    try:
        return await service.save(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health", response_model=ProviderHealthResponse)
async def check_all_provider_health(
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderHealthResponse:
    return await service.health()


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderResponse:
    try:
        return await service.get(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider not found.") from exc


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    request: ProviderUpsertApiRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderResponse:
    try:
        return await service.save(request, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{provider_id}/health", response_model=ProviderHealthResponse)
async def check_provider_health(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderHealthResponse:
    return await service.health(provider_id)


@router.post("/test-connection", response_model=ProviderConnectivityResponse)
async def test_provider_connection(
    request: ProviderConnectivityApiRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderConnectivityResponse:
    try:
        return await service.test_connection(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> None:
    await service.delete(provider_id)


@router.get("/{provider_id}/models", response_model=ProviderModelProfilesResponse)
async def list_provider_models(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderModelProfilesResponse:
    try:
        return await service.list_models(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider not found.") from exc


@router.post("/{provider_id}/models/refresh", response_model=ProviderModelProfilesResponse)
async def refresh_provider_models(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderModelProfilesResponse:
    try:
        return await service.refresh_models(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{provider_id}/models/{model_id}", response_model=ProviderModelProfilesResponse)
async def update_provider_model_profile(
    provider_id: UUID,
    model_id: str,
    request: ProviderModelProfileUpdateRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderModelProfilesResponse:
    updates = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        return await service.update_model_profile(provider_id, model_id, updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider not found.") from exc
