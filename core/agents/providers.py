"""Configurable LLM provider registry and OpenAI-compatible runtime clients."""

from __future__ import annotations

import os
import time
import logging
import urllib.error
import urllib.request
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, Field

from core.agents.model_clients import OpenAICompatibleChatModelClient
from core.agents.runtime import AgentModelClient
from core.contracts.prompts import PromptMessage
from core.persistence import PostgresJsonDocumentStore
logger = logging.getLogger(__name__)


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


class ModelCapabilityProfile(BaseModel):
    provider_id: UUID | None = None
    provider_type: str
    model_id: str
    display_name: str | None = None
    context_window_tokens: int = 4096
    max_input_tokens: int = 2500
    max_output_tokens: int = 1024
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_tools: bool = False
    supports_embeddings: bool = False
    recommended_for_chat: bool = True
    recommended_for_agents: bool = True
    recommended_for_code: bool = False
    compact_mode_required: bool = True
    notes: str | None = None
    detection_source: str = "estimated"
    last_refreshed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    context_window_tokens: int | None = 8192
    max_output_tokens: int | None = 1024
    reserved_output_tokens: int | None = 1024
    max_prompt_tokens: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    model_profiles: dict[str, ModelCapabilityProfile] = Field(default_factory=dict)

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
        if saved.is_default:
            for provider_id, provider in list(self._providers.items()):
                if provider_id != saved.id and provider.is_default:
                    self._providers[provider_id] = provider.model_copy(update={"is_default": False})
        if self._store is not None:
            if saved.is_default:
                for provider in self._providers.values():
                    await self._store.upsert(
                        bucket=self._bucket,
                        document_id=provider.id,
                        key=f"{provider.status.value}:{provider.kind.value}:{provider.name}",
                        payload=provider.model_dump(mode="json"),
                    )
                return saved
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
        default = next((provider for provider in providers if provider.is_default), None)
        if default is not None:
            return default
        return providers[0]

    async def build_client(
        self,
        *,
        agent_name: str | None = None,
        provider_id: UUID | str | None = None,
        model: str | None = None,
        agent_models: dict[str, str] | None = None,
        local_lm_studio_safe_mode: bool = False,
    ) -> AgentModelClient:
        provider = await self.get(UUID(str(provider_id))) if provider_id else await self.active()
        if provider is None:
            raise ValueError(f"Configured provider was not found: {provider_id}")
        model_name = model or (agent_models or {}).get(agent_name or "") or provider.agent_models.get(agent_name or "", provider.default_model)
        logger.info(
            "provider routing: provider=%s kind=%s model=%s response_format_mode=%s",
            provider.name,
            provider.kind.value,
            model_name,
            provider.capabilities.get("response_format_mode", "text"),
        )
        profile = _resolve_profile(provider, model_name)
        reserved_output = provider.reserved_output_tokens or provider.max_output_tokens or 1024
        max_prompt_tokens = provider.max_prompt_tokens
        timeout_seconds = provider.timeout_seconds
        supports_json_schema = bool(provider.capabilities.get("supports_json_schema", False))
        if profile is not None:
            reserved_output = profile.max_output_tokens
            computed_prompt = max(512, int(profile.context_window_tokens) - int(profile.max_output_tokens) - 300)
            max_prompt_tokens = provider.max_prompt_tokens or computed_prompt
            supports_json_schema = bool(profile.supports_json_mode)
            logger.info(
                "model capabilities loaded: provider=%s model=%s context_window=%s max_prompt=%s compact_mode=%s source=%s",
                provider.name,
                model_name,
                profile.context_window_tokens,
                max_prompt_tokens,
                profile.compact_mode_required,
                profile.detection_source,
            )
        if local_lm_studio_safe_mode and provider.kind == ProviderKind.LM_STUDIO:
            timeout_seconds = max(float(timeout_seconds or 60), 180.0)
            if agent_name == "ba":
                max_prompt_tokens = min(int(max_prompt_tokens or 1200), 1200)
                reserved_output = min(int(reserved_output or 700), 700)
        return OpenAICompatibleChatModelClient(
            model=model_name,
            api_key=provider.api_key or _local_api_key(provider),
            base_url=provider.base_url,
            timeout_seconds=timeout_seconds,
            response_format_mode=str(provider.capabilities.get("response_format_mode", "text")),
            supports_json_schema=supports_json_schema,
            supports_text_response_format=bool(provider.capabilities.get("supports_text_response_format", True)),
            headers=provider.headers,
            context_window_tokens=profile.context_window_tokens if profile else provider.context_window_tokens,
            reserved_output_tokens=reserved_output,
            max_prompt_tokens=max_prompt_tokens,
        )

    async def health(self, provider_id: UUID | None = None) -> tuple[ProviderHealth, ...]:
        providers = await self.list()
        if provider_id is not None:
            providers = tuple(provider for provider in providers if provider.id == provider_id)
        checks: list[ProviderHealth] = []
        for provider in providers:
            checks.append(_provider_health(provider))
        return tuple(checks)

    async def delete(self, provider_id: UUID) -> None:
        await self._ensure_seeded()
        self._providers.pop(provider_id, None)
        if self._store is not None:
            await self._store.delete(bucket=self._bucket, document_id=provider_id)

    async def test_connection(self, config: ProviderConfig) -> dict[str, Any]:
        url = _connectivity_url(config)
        started = time.perf_counter()
        request = urllib.request.Request(url, headers=_connectivity_headers(config), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds or 20):
                latency_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "status": "success",
                    "latency_ms": latency_ms,
                    "message": "Provider endpoint is reachable.",
                    "url": url,
                    "capabilities": _provider_capabilities(config),
                    "models": [profile.model_dump(mode="json") for profile in (await self.discover_models(config))],
                }
        except urllib.error.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            # 401/403 still prove network reachability and auth validation path.
            if exc.code in {401, 403}:
                return {
                    "status": "warning",
                    "latency_ms": latency_ms,
                    "message": f"Endpoint reachable but authentication failed ({exc.code}).",
                    "url": url,
                    "capabilities": _provider_capabilities(config),
                    "models": [profile.model_dump(mode="json") for profile in (await self.discover_models(config))],
                }
            return {
                "status": "failed",
                "latency_ms": latency_ms,
                "message": f"Endpoint returned HTTP {exc.code}.",
                "url": url,
            }
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "status": "failed",
                "latency_ms": latency_ms,
                "message": str(exc),
                "url": url,
            }

    async def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        for provider in _providers_from_environment():
            self._providers.setdefault(provider.id, provider)

    async def discover_models(self, provider: ProviderConfig) -> tuple[ModelCapabilityProfile, ...]:
        if provider.kind == ProviderKind.OLLAMA:
            return await self._discover_ollama_models(provider)
        return await self._discover_openai_compatible_models(provider)

    async def refresh_models(self, provider_id: UUID) -> tuple[ModelCapabilityProfile, ...]:
        provider = await self.get(provider_id)
        if provider is None:
            raise ValueError(f"Configured provider was not found: {provider_id}")
        models = await self.discover_models(provider)
        updated = provider.model_copy(
            update={
                "model_profiles": {profile.model_id: profile.model_copy(update={"provider_id": provider.id}) for profile in models},
                "updated_at": datetime.now(timezone.utc),
            }
        )
        await self.upsert(updated)
        return models

    async def update_model_profile(self, provider_id: UUID, model_id: str, updates: dict[str, Any]) -> ModelCapabilityProfile:
        provider = await self.get(provider_id)
        if provider is None:
            raise ValueError(f"Configured provider was not found: {provider_id}")
        current = provider.model_profiles.get(model_id) or _default_model_profile(provider, model_id, detection_source="manual")
        merged = current.model_copy(update={**updates, "provider_id": provider_id, "model_id": model_id, "provider_type": provider.kind.value, "detection_source": "manual"})
        profiles = dict(provider.model_profiles)
        profiles[model_id] = merged
        await self.upsert(provider.model_copy(update={"model_profiles": profiles}))
        return merged

    async def _discover_openai_compatible_models(self, provider: ProviderConfig) -> tuple[ModelCapabilityProfile, ...]:
        url = _connectivity_url(provider)
        request = urllib.request.Request(url, headers=_connectivity_headers(provider), method="GET")
        with urllib.request.urlopen(request, timeout=provider.timeout_seconds or 20) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
        items = payload.get("data", []) if isinstance(payload, dict) else []
        profiles: list[ModelCapabilityProfile] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("id", "")).strip()
                if not model_id:
                    continue
                profiles.append(_default_model_profile(provider, model_id, detection_source="discovered"))
        if not profiles and provider.default_model:
            profiles.append(_default_model_profile(provider, provider.default_model, detection_source="fallback"))
        return tuple(profiles)

    async def _discover_ollama_models(self, provider: ProviderConfig) -> tuple[ModelCapabilityProfile, ...]:
        if not provider.base_url:
            return tuple()
        base = provider.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/api/tags"
        request = urllib.request.Request(url, headers=_connectivity_headers(provider), method="GET")
        with urllib.request.urlopen(request, timeout=provider.timeout_seconds or 20) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
        models = payload.get("models", []) if isinstance(payload, dict) else []
        profiles: list[ModelCapabilityProfile] = []
        if isinstance(models, list):
            for item in models:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("name", "")).strip()
                if not model_id:
                    continue
                details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
                profile = _default_model_profile(provider, model_id, detection_source="discovered")
                family = str(details.get("family", ""))
                profile = profile.model_copy(
                    update={
                        "display_name": str(item.get("model") or model_id),
                        "notes": f"Ollama family: {family}" if family else profile.notes,
                    }
                )
                profiles.append(profile)
        if not profiles and provider.default_model:
            profiles.append(_default_model_profile(provider, provider.default_model, detection_source="fallback"))
        return tuple(profiles)


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
            local_lm_studio_safe_mode=bool(metadata.get("local_lm_studio_safe_mode", False)),
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
                id=_stable_provider_id("openai"),
                kind=ProviderKind.OPENAI,
                api_key=openai_key,
                base_url=os.getenv("OPENAI_BASE_URL") or None,
                default_model=os.getenv("OPENAI_CODEX_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5",
                capabilities=_provider_capabilities_from_kind(ProviderKind.OPENAI),
            )
        )
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        providers.append(
            ProviderConfig(
                name="OpenRouter",
                id=_stable_provider_id("openrouter"),
                kind=ProviderKind.OPENROUTER,
                api_key=openrouter_key,
                base_url=os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
                default_model=os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
                capabilities=_provider_capabilities_from_kind(ProviderKind.OPENROUTER),
            )
        )
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        providers.append(
            ProviderConfig(
                name="Ollama",
                id=_stable_provider_id("ollama"),
                kind=ProviderKind.OLLAMA,
                base_url=ollama_url.rstrip("/") + "/v1",
                default_model=os.getenv("OLLAMA_MODEL") or "llama3.1",
                capabilities=_provider_capabilities_from_kind(ProviderKind.OLLAMA),
            )
        )
    lm_studio_url = os.getenv("LM_STUDIO_BASE_URL")
    if lm_studio_url:
        providers.append(
            ProviderConfig(
                name="LM Studio",
                id=_stable_provider_id("lm_studio"),
                kind=ProviderKind.LM_STUDIO,
                base_url=lm_studio_url.rstrip("/") + "/v1",
                default_model=os.getenv("LM_STUDIO_MODEL") or "local-model",
                capabilities=_provider_capabilities_from_kind(ProviderKind.LM_STUDIO),
            )
        )
    custom_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    if custom_url:
        providers.append(
            ProviderConfig(
                name=os.getenv("OPENAI_COMPATIBLE_PROVIDER_NAME") or "Custom OpenAI Compatible",
                id=_stable_provider_id("custom"),
                kind=ProviderKind.CUSTOM,
                api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
                base_url=custom_url,
                default_model=os.getenv("OPENAI_COMPATIBLE_MODEL") or "default",
                capabilities=_provider_capabilities_from_kind(ProviderKind.CUSTOM),
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


def _stable_provider_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"provider:{name}")


def _connectivity_url(provider: ProviderConfig) -> str:
    if provider.kind == ProviderKind.OPENAI:
        base = provider.base_url or "https://api.openai.com/v1"
    elif provider.kind in {ProviderKind.OLLAMA, ProviderKind.LM_STUDIO, ProviderKind.CUSTOM, ProviderKind.OPENROUTER, ProviderKind.CURSOR, ProviderKind.LOCAL}:
        base = provider.base_url or ""
    else:
        base = provider.base_url or ""
    base = base.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def _connectivity_headers(provider: ProviderConfig) -> dict[str, str]:
    headers = {"Accept": "application/json", **provider.headers}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    return headers


def _provider_capabilities(provider: ProviderConfig) -> dict[str, Any]:
    return provider.capabilities or _provider_capabilities_from_kind(provider.kind)


def _provider_capabilities_from_kind(kind: ProviderKind) -> dict[str, Any]:
    # Conservative defaults for compatibility-first behavior.
    base = {
        "supports_response_format": True,
        "supports_json_schema": False,
        "supports_text_response_format": True,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_structured_outputs": False,
        "response_format_mode": "text",
    }
    if kind == ProviderKind.OPENAI:
        return {**base, "supports_json_schema": True, "supports_structured_outputs": True}
    return base


def _default_model_profile(
    provider: ProviderConfig,
    model_id: str,
    *,
    detection_source: str,
) -> ModelCapabilityProfile:
    context_window = int(provider.context_window_tokens or 4096)
    max_output = int(provider.max_output_tokens or provider.reserved_output_tokens or 1024)
    max_input = max(256, context_window - max_output - 300)
    caps = _provider_capabilities(provider)
    compact = context_window <= 4096
    return ModelCapabilityProfile(
        provider_id=provider.id,
        provider_type=provider.kind.value,
        model_id=model_id,
        display_name=model_id,
        context_window_tokens=context_window,
        max_input_tokens=max_input,
        max_output_tokens=max_output,
        supports_streaming=bool(caps.get("supports_streaming", True)),
        supports_json_mode=bool(caps.get("supports_json_schema", False)),
        supports_tools=bool(caps.get("supports_tools", False)),
        supports_embeddings=False,
        recommended_for_chat=True,
        recommended_for_agents=not compact,
        recommended_for_code=not compact and context_window >= 8192,
        compact_mode_required=compact,
        notes="Manual/estimated profile." if detection_source != "discovered" else "Discovered from provider API.",
        detection_source=detection_source,
    )


def _resolve_profile(provider: ProviderConfig, model_name: str) -> ModelCapabilityProfile | None:
    profile = provider.model_profiles.get(model_name)
    if profile is not None:
        return profile
    if provider.default_model and provider.default_model in provider.model_profiles:
        return provider.model_profiles[provider.default_model]
    return None
