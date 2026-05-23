"""Application service for configurable LLM providers."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.schemas import ProviderConnectivityApiRequest, ProviderConnectivityResponse, ProviderHealthResponse, ProviderListResponse, ProviderResponse, ProviderUpsertApiRequest
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
            headers=request.headers,
            is_default=request.is_default or (existing.is_default if existing else not has_default),
            metadata=request.metadata,
            capabilities=(existing.capabilities if existing else {}),
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
            headers=request.headers,
        )
        result = await self._registry.test_connection(candidate)
        return ProviderConnectivityResponse(result=result)
