"""Application service for configurable LLM providers."""

from __future__ import annotations

import os
import logging
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

from app.schemas import LMStudioLoadModelRequest, ProviderConnectivityApiRequest, ProviderConnectivityResponse, ProviderHealthResponse, ProviderListResponse, ProviderModelAssignRequest, ProviderModelProfilesResponse, ProviderResponse, ProviderUpsertApiRequest, ProviderWorkflowPreflightRequest, ProviderWorkflowPreflightResponse
from core.agents.providers import ProviderConfig, ProviderKind, ProviderRegistry, ProviderStatus

logger = logging.getLogger(__name__)


class ProviderApplicationService:
    """Manages LLM provider configuration for runtime routing."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry
        self._local_model_management_enabled = os.getenv("ENABLE_LOCAL_MODEL_MANAGEMENT", "").strip().lower() in {"1", "true", "yes", "on"}

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    async def list(self) -> ProviderListResponse:
        return ProviderListResponse(
            providers=tuple(provider.public_dict() for provider in await self._registry.list())
        )

    async def save(self, request: ProviderUpsertApiRequest, provider_id: UUID | None = None) -> ProviderResponse:
        existing = await self._registry.get(provider_id) if provider_id is not None else None
        all_providers = await self._registry.list()
        if existing is None and provider_id is None:
            for provider in all_providers:
                if provider.name.strip().lower() == request.name.strip().lower():
                    existing = provider
                    provider_id = provider.id
                    break
        has_default = any(provider.is_default for provider in all_providers)
        incoming_api_key = request.api_key
        if _is_masked_secret(incoming_api_key):
            incoming_api_key = None
        normalized_base_url, management_base_url = _normalize_local_runtime_urls(request.base_url, request.kind)
        metadata = dict(request.metadata or {})
        if management_base_url is not None:
            metadata.setdefault("management_base_url", management_base_url)
            metadata.setdefault("inference_base_url", normalized_base_url)
            metadata.setdefault("lm_studio_auth_mode", str(metadata.get("lm_studio_auth_mode") or "raw"))
        resolved_default_model = request.default_model or (existing.default_model if existing else None) or ("local-model" if request.kind in {"lm_studio", "local_lm_studio"} else "default")
        provider = ProviderConfig(
            id=provider_id or uuid4(),
            name=request.name,
            kind=ProviderKind(request.kind),
            base_url=normalized_base_url,
            api_key=incoming_api_key if incoming_api_key is not None else existing.api_key if existing else None,
            default_model=resolved_default_model,
            status=ProviderStatus(request.status),
            agent_models=request.agent_models,
            timeout_seconds=request.timeout_seconds,
            context_window_tokens=request.context_window_tokens if request.context_window_tokens is not None else (existing.context_window_tokens if existing else 8192),
            max_output_tokens=request.max_output_tokens if request.max_output_tokens is not None else (existing.max_output_tokens if existing else 1024),
            reserved_output_tokens=request.reserved_output_tokens if request.reserved_output_tokens is not None else (existing.reserved_output_tokens if existing else 1024),
            max_prompt_tokens=request.max_prompt_tokens if request.max_prompt_tokens is not None else (existing.max_prompt_tokens if existing else None),
            headers=request.headers,
            is_default=request.is_default or (existing.is_default if existing else not has_default),
            metadata=metadata,
            capabilities=(existing.capabilities if existing else {}),
            model_profiles=(existing.model_profiles if existing else {}),
        )
        saved = await self._registry.upsert(provider)
        return ProviderResponse(provider=saved.public_dict())

    async def get(self, provider_id: UUID) -> ProviderResponse:
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        return ProviderResponse(provider=provider.public_dict())

    async def health(self, provider_id: UUID | None = None) -> ProviderHealthResponse:
        return ProviderHealthResponse(
            checks=tuple(check.model_dump(mode="json") for check in await self._registry.health(provider_id))
        )

    async def delete(self, provider_id: UUID) -> None:
        await self._registry.delete(provider_id)

    async def test_connection(self, request: ProviderConnectivityApiRequest) -> ProviderConnectivityResponse:
        normalized_base_url, management_base_url = _normalize_local_runtime_urls(request.base_url, request.kind)
        metadata: dict[str, object] = {}
        if management_base_url is not None:
            metadata["management_base_url"] = request.management_base_url or management_base_url
            metadata["inference_base_url"] = request.inference_base_url or normalized_base_url
            metadata["lm_studio_auth_mode"] = str(request.lm_studio_auth_mode or "raw")
        resolved_default_model = request.default_model or ("local-model" if request.kind in {"lm_studio", "local_lm_studio"} else "default")
        candidate = ProviderConfig(
            name=request.name,
            kind=ProviderKind(request.kind),
            base_url=request.inference_base_url or normalized_base_url,
            api_key=request.api_key,
            default_model=resolved_default_model,
            timeout_seconds=request.timeout_seconds,
            context_window_tokens=request.context_window_tokens,
            max_output_tokens=request.max_output_tokens,
            reserved_output_tokens=request.reserved_output_tokens,
            max_prompt_tokens=request.max_prompt_tokens,
            headers=request.headers,
            metadata=metadata,
        )
        result = await self._registry.test_connection(candidate)
        return ProviderConnectivityResponse(result=result)

    async def list_models(self, provider_id: UUID) -> ProviderModelProfilesResponse:
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        if not provider.model_profiles:
            profiles = await self._registry.discover_models(provider)
            return ProviderModelProfilesResponse(models=tuple(item.model_dump(mode="json") for item in profiles))
        return ProviderModelProfilesResponse(
            models=tuple(item.model_dump(mode="json") for item in provider.model_profiles.values())
        )

    async def refresh_models(self, provider_id: UUID) -> ProviderModelProfilesResponse:
        try:
            profiles = await self._registry.refresh_models(provider_id)
        except ValueError as exc:
            if "was not found" in str(exc):
                raise KeyError(str(provider_id)) from exc
            raise
        return ProviderModelProfilesResponse(models=tuple(item.model_dump(mode="json") for item in profiles))

    async def update_model_profile(self, provider_id: UUID, model_id: str, updates: dict[str, object]) -> ProviderModelProfilesResponse:
        await self._registry.update_model_profile(provider_id, model_id, updates)
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        return ProviderModelProfilesResponse(
            models=tuple(item.model_dump(mode="json") for item in provider.model_profiles.values())
        )

    def assert_local_model_management_enabled(self) -> None:
        if not self._local_model_management_enabled:
            raise ValueError("local_model_management_disabled: Set ENABLE_LOCAL_MODEL_MANAGEMENT=true for trusted deployments.")

    async def assign_agent_model(
        self,
        provider_id: UUID,
        *,
        agent_name: str,
        request: ProviderModelAssignRequest,
    ) -> ProviderResponse:
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        agent_models = dict(provider.agent_models)
        agent_models[agent_name] = request.model_id
        saved = await self._registry.upsert(provider.model_copy(update={"agent_models": agent_models}))
        return ProviderResponse(provider=saved.public_dict())

    async def lmstudio_runtime_models(self, provider_id: UUID) -> dict[str, object]:
        self.assert_local_model_management_enabled()
        return await self._registry.lmstudio_list_runtime_models(provider_id)

    async def lmstudio_load_model(self, provider_id: UUID, request: LMStudioLoadModelRequest) -> ProviderModelProfilesResponse:
        logger.info(
            "local_model_load_request_received provider_id=%s selected_model_id=%s context_length=%s feature_flag_enabled=%s",
            provider_id,
            request.model_id,
            request.context_length,
            self._local_model_management_enabled,
        )
        self.assert_local_model_management_enabled()
        await self._registry.lmstudio_load_model(
            provider_id,
            model_id=request.model_id,
            context_length=request.context_length,
            max_output_tokens=request.max_output_tokens,
            parallel_slots=request.parallel_slots,
            gpu_offload=request.gpu_offload,
            temperature=request.temperature,
            streaming_enabled=request.streaming_enabled,
            flash_attention=request.flash_attention,
            echo_load_config=request.echo_load_config,
        )
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        return ProviderModelProfilesResponse(models=tuple(item.model_dump(mode="json") for item in provider.model_profiles.values()))

    async def lmstudio_unload_model(self, provider_id: UUID, *, model_id: str) -> ProviderModelProfilesResponse:
        logger.info(
            "local_model_unload_request_received provider_id=%s selected_model_id=%s feature_flag_enabled=%s",
            provider_id,
            model_id,
            self._local_model_management_enabled,
        )
        self.assert_local_model_management_enabled()
        await self._registry.lmstudio_unload_model(provider_id, model_id=model_id)
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        return ProviderModelProfilesResponse(models=tuple(item.model_dump(mode="json") for item in provider.model_profiles.values()))

    async def lmstudio_download_model(self, provider_id: UUID, *, model_id: str) -> ProviderConnectivityResponse:
        self.assert_local_model_management_enabled()
        result = await self._registry.lmstudio_download_model(provider_id, model_id=model_id)
        return ProviderConnectivityResponse(result=result)

    async def lmstudio_download_status(self, provider_id: UUID, *, download_id: str | None = None, model: str | None = None) -> ProviderConnectivityResponse:
        self.assert_local_model_management_enabled()
        result = await self._registry.lmstudio_download_status(provider_id, download_id=download_id, model=model)
        return ProviderConnectivityResponse(result=result)

    async def preflight(self, provider_id: UUID, request: ProviderWorkflowPreflightRequest) -> ProviderWorkflowPreflightResponse:
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        warnings: list[str] = []
        recommendations: list[str] = []
        required_agents = tuple(request.required_agents) or ("ba", "architect")
        for agent in required_agents:
            model_id = provider.agent_models.get(agent, provider.default_model)
            profile = provider.model_profiles.get(model_id)
            if profile is None:
                warnings.append(f"{agent}: model profile not found for '{model_id}'.")
                recommendations.append(f"Refresh models and assign a discovered model to {agent}.")
                continue
            if provider.kind in {ProviderKind.LM_STUDIO, ProviderKind.LOCAL_LM_STUDIO} and profile.runtime_status != "loaded":
                warnings.append(f"{agent}: model '{model_id}' is not loaded.")
                recommendations.append(f"Load '{model_id}' before starting workflow.")
            if profile.context_window_tokens <= 4096:
                warnings.append(f"{agent}: context window is {profile.context_window_tokens}, local compact mode is recommended.")
                recommendations.append("Use BA-only or BA+Architect mode, or increase context to 8192 if stable.")
        ok = len(warnings) == 0
        return ProviderWorkflowPreflightResponse(ok=ok, warnings=tuple(warnings), recommendations=tuple(recommendations))


def _is_masked_secret(value: str | None) -> bool:
    if value is None:
        return False
    candidate = value.strip()
    if not candidate:
        return False
    return "..." in candidate or "*" in candidate


def _normalize_local_runtime_urls(base_url: str | None, kind: str) -> tuple[str | None, str | None]:
    if kind not in {"lm_studio", "local_lm_studio"}:
        return base_url, None
    if not base_url:
        return None, None
    raw = base_url.strip().rstrip("/")
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[: -len("/api/v1")]
    elif path.endswith("/v1"):
        path = path[: -len("/v1")]
    management_base = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
    inference_base = f"{management_base}/v1"
    return inference_base, management_base
