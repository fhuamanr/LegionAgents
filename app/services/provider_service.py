"""Application service for configurable LLM providers."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.schemas import ProviderConnectivityApiRequest, ProviderConnectivityResponse, ProviderHealthResponse, ProviderListResponse, ProviderModelProfilesResponse, ProviderResponse, ProviderUpsertApiRequest
from core.agents.providers import ProviderConfig, ProviderKind, ProviderRegistry, ProviderStatus


class ProviderApplicationService:
    """Manages LLM provider configuration for runtime routing."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

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
        provider = ProviderConfig(
            id=provider_id or uuid4(),
            name=request.name,
            kind=ProviderKind(request.kind),
            base_url=request.base_url,
            api_key=request.api_key if request.api_key is not None else existing.api_key if existing else None,
            default_model=request.default_model,
            status=ProviderStatus(request.status),
            agent_models=request.agent_models,
            timeout_seconds=request.timeout_seconds,
            context_window_tokens=request.context_window_tokens if request.context_window_tokens is not None else (existing.context_window_tokens if existing else 8192),
            max_output_tokens=request.max_output_tokens if request.max_output_tokens is not None else (existing.max_output_tokens if existing else 1024),
            reserved_output_tokens=request.reserved_output_tokens if request.reserved_output_tokens is not None else (existing.reserved_output_tokens if existing else 1024),
            max_prompt_tokens=request.max_prompt_tokens if request.max_prompt_tokens is not None else (existing.max_prompt_tokens if existing else None),
            headers=request.headers,
            is_default=request.is_default or (existing.is_default if existing else not has_default),
            metadata=request.metadata,
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
        candidate = ProviderConfig(
            name=request.name,
            kind=ProviderKind(request.kind),
            base_url=request.base_url,
            api_key=request.api_key,
            default_model=request.default_model,
            timeout_seconds=request.timeout_seconds,
            context_window_tokens=request.context_window_tokens,
            max_output_tokens=request.max_output_tokens,
            reserved_output_tokens=request.reserved_output_tokens,
            max_prompt_tokens=request.max_prompt_tokens,
            headers=request.headers,
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
        profiles = await self._registry.refresh_models(provider_id)
        return ProviderModelProfilesResponse(models=tuple(item.model_dump(mode="json") for item in profiles))

    async def update_model_profile(self, provider_id: UUID, model_id: str, updates: dict[str, object]) -> ProviderModelProfilesResponse:
        await self._registry.update_model_profile(provider_id, model_id, updates)
        provider = await self._registry.get(provider_id)
        if provider is None:
            raise KeyError(str(provider_id))
        return ProviderModelProfilesResponse(
            models=tuple(item.model_dump(mode="json") for item in provider.model_profiles.values())
        )
