"""Configurable LLM provider registry and OpenAI-compatible runtime clients."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.agents.model_clients import OpenAICompatibleChatModelClient
from core.agents.runtime import AgentModelClient
from core.contracts.prompts import PromptMessage
from core.persistence import PostgresJsonDocumentStore


class ProviderKind(StrEnum):
    OPENAI = "openai"
    CURSOR = "cursor"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    LOCAL = "local"
    CUSTOM = "custom"


class ProviderStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ProviderConfig(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    kind: ProviderKind
    base_url: str | None = None
    api_key: str | None = None
    default_model: str
    status: ProviderStatus = ProviderStatus.ACTIVE
    agent_models: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = 60
    headers: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["api_key"] = self.masked_api_key
        payload["configured"] = bool(self.api_key or self.kind in _LOCAL_PROVIDER_KINDS)
        return payload

    @property
    def masked_api_key(self) -> str | None:
        if not self.api_key:
            return None
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


class ProviderHealth(BaseModel):
    provider_id: UUID
    status: str
    message: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderRegistry:
    """Persists provider configuration and exposes routing helpers."""

    _bucket = "llm_providers"

    def __init__(self, store: PostgresJsonDocumentStore | None = None) -> None:
        self._store = store
        self._providers: dict[UUID, ProviderConfig] = {}
        self._seeded = False

    async def upsert(self, config: ProviderConfig) -> ProviderConfig:
        now = datetime.now(timezone.utc)
        existing = await self.get(config.id)
        saved = config.model_copy(
            update={
                "created_at": existing.created_at if existing else config.created_at,
                "updated_at": now,
            }
        )
        self._providers[saved.id] = saved
        if self._store is not None:
            await self._store.upsert(
                bucket=self._bucket,
                document_id=saved.id,
                key=f"{saved.status.value}:{saved.kind.value}:{saved.name}",
                payload=saved.model_dump(mode="json"),
            )
        return saved

    async def get(self, provider_id: UUID) -> ProviderConfig | None:
        await self._ensure_seeded()
        if provider_id in self._providers:
            return self._providers[provider_id]
        if self._store is None:
            return None
        try:
            provider = ProviderConfig.model_validate(
                await self._store.get(bucket=self._bucket, document_id=provider_id)
            )
        except KeyError:
            return None
        self._providers[provider.id] = provider
        return provider

    async def list(self) -> tuple[ProviderConfig, ...]:
        await self._ensure_seeded()
        if self._store is not None:
            for payload in await self._store.list(bucket=self._bucket):
                provider = ProviderConfig.model_validate(payload)
                self._providers[provider.id] = provider
        return tuple(sorted(self._providers.values(), key=lambda item: (item.status.value, item.name)))

    async def active(self) -> ProviderConfig:
        providers = [provider for provider in await self.list() if provider.status == ProviderStatus.ACTIVE]
        if not providers:
            raise ValueError("No active LLM provider is configured.")
        return providers[0]

    async def build_client(
        self,
        *,
        agent_name: str | None = None,
        provider_id: UUID | str | None = None,
        model: str | None = None,
        agent_models: dict[str, str] | None = None,
    ) -> AgentModelClient:
        provider = await self.get(UUID(str(provider_id))) if provider_id else await self.active()
        if provider is None:
            raise ValueError(f"Configured provider was not found: {provider_id}")
        model_name = model or (agent_models or {}).get(agent_name or "") or provider.agent_models.get(agent_name or "", provider.default_model)
        return OpenAICompatibleChatModelClient(
            model=model_name,
            api_key=provider.api_key or _local_api_key(provider),
            base_url=provider.base_url,
            timeout_seconds=provider.timeout_seconds,
            headers=provider.headers,
        )

    async def health(self, provider_id: UUID | None = None) -> tuple[ProviderHealth, ...]:
        providers = await self.list()
        if provider_id is not None:
            providers = tuple(provider for provider in providers if provider.id == provider_id)
        checks: list[ProviderHealth] = []
        for provider in providers:
            checks.append(_provider_health(provider))
        return tuple(checks)

    async def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        for provider in _providers_from_environment():
            self._providers.setdefault(provider.id, provider)


class RoutingModelClient(AgentModelClient):
    """Model client that routes each agent to the configured provider/model."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        agent_name = _agent_name_from_messages(messages)
        client = await self._registry.build_client(agent_name=agent_name)
        return await client.complete(messages)

    async def complete_for_runtime(self, context: Any) -> str:
        client = await self._client_for_context(context)
        return await client.complete(context.prompt_messages)

    async def stream_complete(self, messages: tuple[PromptMessage, ...]):
        agent_name = _agent_name_from_messages(messages)
        client = await self._registry.build_client(agent_name=agent_name)
        if hasattr(client, "stream_complete"):
            async for chunk in client.stream_complete(messages):  # type: ignore[attr-defined]
                yield chunk
            return
        yield await client.complete(messages)

    async def stream_for_runtime(self, context: Any):
        client = await self._client_for_context(context)
        if hasattr(client, "stream_complete"):
            async for chunk in client.stream_complete(context.prompt_messages):  # type: ignore[attr-defined]
                yield chunk
            return
        yield await client.complete(context.prompt_messages)

    async def _client_for_context(self, context: Any) -> AgentModelClient:
        metadata = dict(getattr(context.request, "metadata", {}))
        agent_name = getattr(context.agent_config, "name", None)
        agent_models = metadata.get("agent_models")
        return await self._registry.build_client(
            agent_name=agent_name,
            provider_id=metadata.get("provider_id"),
            model=metadata.get("model") or metadata.get(f"{agent_name}_model"),
            agent_models=agent_models if isinstance(agent_models, dict) else None,
        )


_LOCAL_PROVIDER_KINDS = {ProviderKind.OLLAMA, ProviderKind.LM_STUDIO, ProviderKind.LOCAL}


def _provider_health(provider: ProviderConfig) -> ProviderHealth:
    if provider.status == ProviderStatus.DISABLED:
        return ProviderHealth(provider_id=provider.id, status="disabled", message="Provider is disabled.")
    if not provider.default_model.strip():
        return ProviderHealth(provider_id=provider.id, status="failed", message="Default model is required.")
    if provider.kind not in _LOCAL_PROVIDER_KINDS and not provider.api_key:
        return ProviderHealth(provider_id=provider.id, status="warning", message="API key is not configured.")
    if provider.kind in {ProviderKind.CUSTOM, ProviderKind.CURSOR, ProviderKind.OPENROUTER, ProviderKind.OLLAMA, ProviderKind.LM_STUDIO, ProviderKind.LOCAL} and not provider.base_url:
        return ProviderHealth(provider_id=provider.id, status="warning", message="Base URL is not configured.")
    return ProviderHealth(provider_id=provider.id, status="ok", message="Provider configuration is ready.")


def _providers_from_environment() -> tuple[ProviderConfig, ...]:
    providers: list[ProviderConfig] = []
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        providers.append(
            ProviderConfig(
                name="OpenAI",
                kind=ProviderKind.OPENAI,
                api_key=openai_key,
                base_url=os.getenv("OPENAI_BASE_URL") or None,
                default_model=os.getenv("OPENAI_CODEX_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5",
            )
        )
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        providers.append(
            ProviderConfig(
                name="OpenRouter",
                kind=ProviderKind.OPENROUTER,
                api_key=openrouter_key,
                base_url=os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
                default_model=os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
            )
        )
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        providers.append(
            ProviderConfig(
                name="Ollama",
                kind=ProviderKind.OLLAMA,
                base_url=ollama_url.rstrip("/") + "/v1",
                default_model=os.getenv("OLLAMA_MODEL") or "llama3.1",
            )
        )
    lm_studio_url = os.getenv("LM_STUDIO_BASE_URL")
    if lm_studio_url:
        providers.append(
            ProviderConfig(
                name="LM Studio",
                kind=ProviderKind.LM_STUDIO,
                base_url=lm_studio_url.rstrip("/") + "/v1",
                default_model=os.getenv("LM_STUDIO_MODEL") or "local-model",
            )
        )
    custom_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    if custom_url:
        providers.append(
            ProviderConfig(
                name=os.getenv("OPENAI_COMPATIBLE_PROVIDER_NAME") or "Custom OpenAI Compatible",
                kind=ProviderKind.CUSTOM,
                api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
                base_url=custom_url,
                default_model=os.getenv("OPENAI_COMPATIBLE_MODEL") or "default",
            )
        )
    return tuple(providers)


def _local_api_key(provider: ProviderConfig) -> str:
    return provider.api_key or "local-llm"


def _agent_name_from_messages(messages: tuple[PromptMessage, ...]) -> str | None:
    for message in messages:
        marker = "Agent name:"
        if marker not in message.content:
            continue
        after = message.content.split(marker, 1)[1].strip()
        return after.split(".", 1)[0].strip()
    return None
