"""LLM provider management APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.container import get_provider_service
from app.dependencies.security import require_permissions
from app.schemas import LMStudioDownloadModelRequest, LMStudioLoadModelRequest, LMStudioRuntimeModelsResponse, LMStudioUnloadModelRequest, ProviderConnectivityApiRequest, ProviderConnectivityResponse, ProviderHealthResponse, ProviderListResponse, ProviderModelAssignRequest, ProviderModelProfileUpdateRequest, ProviderModelProfilesResponse, ProviderResponse, ProviderUpsertApiRequest, ProviderWorkflowPreflightRequest, ProviderWorkflowPreflightResponse
from app.services.provider_service import ProviderApplicationService
from core.contracts.security import SecurityPermission

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


@router.get("/{provider_id}/runtime-models", response_model=LMStudioRuntimeModelsResponse)
async def lmstudio_runtime_models(
    provider_id: UUID,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> LMStudioRuntimeModelsResponse:
    try:
        payload = await service.lmstudio_runtime_models(provider_id)
        available = payload.get("available", {}).get("data", []) if isinstance(payload.get("available"), dict) else []
        loaded = payload.get("loaded", {}).get("data", []) if isinstance(payload.get("loaded"), dict) else payload.get("loaded", {}).get("models", []) if isinstance(payload.get("loaded"), dict) else []
        return LMStudioRuntimeModelsResponse(
            available=tuple(item for item in available if isinstance(item, dict)),
            loaded=tuple(item for item in loaded if isinstance(item, dict)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{provider_id}/runtime-models/load", response_model=ProviderModelProfilesResponse)
async def lmstudio_load_model(
    provider_id: UUID,
    request: LMStudioLoadModelRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> ProviderModelProfilesResponse:
    try:
        return await service.lmstudio_load_model(provider_id, request)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{provider_id}/runtime-models/unload", response_model=ProviderModelProfilesResponse)
async def lmstudio_unload_model(
    provider_id: UUID,
    request: LMStudioUnloadModelRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> ProviderModelProfilesResponse:
    try:
        return await service.lmstudio_unload_model(provider_id, model_id=request.model_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{provider_id}/runtime-models/download", response_model=ProviderConnectivityResponse)
async def lmstudio_download_model(
    provider_id: UUID,
    request: LMStudioDownloadModelRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> ProviderConnectivityResponse:
    try:
        return await service.lmstudio_download_model(provider_id, model_id=request.model_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{provider_id}/runtime-models/download-status", response_model=ProviderConnectivityResponse)
async def lmstudio_download_status(
    provider_id: UUID,
    download_id: str | None = None,
    model: str | None = None,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> ProviderConnectivityResponse:
    try:
        return await service.lmstudio_download_status(provider_id, download_id=download_id, model=model)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{provider_id}/agents/{agent_name}/model", response_model=ProviderResponse)
async def assign_agent_model(
    provider_id: UUID,
    agent_name: str,
    request: ProviderModelAssignRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
    _: object = Depends(require_permissions(SecurityPermission.GOVERNANCE_WRITE, any_permission=True)),
) -> ProviderResponse:
    try:
        return await service.assign_agent_model(provider_id, agent_name=agent_name, request=request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider not found.") from exc


@router.post("/{provider_id}/preflight", response_model=ProviderWorkflowPreflightResponse)
async def provider_preflight(
    provider_id: UUID,
    request: ProviderWorkflowPreflightRequest,
    service: ProviderApplicationService = Depends(get_provider_service),
) -> ProviderWorkflowPreflightResponse:
    try:
        return await service.preflight(provider_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Provider not found.") from exc
