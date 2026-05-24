"""Per-agent runtime profile persistence and defaults."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.persistence import PostgresJsonDocumentStore


class AgentRuntimeProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    agent_name: str
    provider_id: str | None = None
    model: str | None = None
    context_window_tokens: int | None = None
    max_prompt_tokens: int | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    streaming_enabled: bool = False
    compact_mode_enabled: bool = True
    retry_policy: str = "deterministic_no_retry"
    parser_strategy: str = "json"
    handoff_summary_max_tokens: int = 500
    enable_repo_context: bool = False
    enable_governance_context: bool = False
    enable_examples: bool = False
    enable_diagrams: bool = False
    fallback_provider_id: str | None = None
    fallback_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentRuntimeProfileRepository:
    _bucket = "agent_runtime_profiles"

    def __init__(self, store: PostgresJsonDocumentStore | None = None) -> None:
        self._store = store
        self._memory: dict[str, AgentRuntimeProfile] = {}

    async def list(self) -> tuple[AgentRuntimeProfile, ...]:
        if self._store is not None:
            for payload in await self._store.list(bucket=self._bucket):
                profile = AgentRuntimeProfile.model_validate(payload)
                self._memory[profile.agent_name] = profile
        if not self._memory:
            for profile in _default_profiles():
                self._memory[profile.agent_name] = profile
        return tuple(sorted(self._memory.values(), key=lambda item: item.agent_name))

    async def get(self, agent_name: str) -> AgentRuntimeProfile:
        await self.list()
        return self._memory.get(agent_name) or next(item for item in _default_profiles() if item.agent_name == agent_name)

    async def upsert(self, profile: AgentRuntimeProfile) -> AgentRuntimeProfile:
        updated = profile.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._memory[updated.agent_name] = updated
        if self._store is not None:
            await self._store.upsert(
                bucket=self._bucket,
                document_id=updated.id,
                key=updated.agent_name,
                payload=updated.model_dump(mode="json"),
            )
        return updated


def _default_profiles() -> tuple[AgentRuntimeProfile, ...]:
    return (
        AgentRuntimeProfile(agent_name="ba", max_prompt_tokens=900, max_output_tokens=450, handoff_summary_max_tokens=500, parser_strategy="markdown_sections"),
        AgentRuntimeProfile(agent_name="architect", max_prompt_tokens=1200, max_output_tokens=600, handoff_summary_max_tokens=700, parser_strategy="markdown_sections"),
        AgentRuntimeProfile(agent_name="developer", max_prompt_tokens=1500, max_output_tokens=700, handoff_summary_max_tokens=700),
        AgentRuntimeProfile(agent_name="qa", max_prompt_tokens=1000, max_output_tokens=500, handoff_summary_max_tokens=500),
        AgentRuntimeProfile(agent_name="docs", max_prompt_tokens=900, max_output_tokens=500, handoff_summary_max_tokens=400),
        AgentRuntimeProfile(agent_name="pr", max_prompt_tokens=700, max_output_tokens=300, handoff_summary_max_tokens=300),
    )
