"""Context engineering models."""

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field

from core.contracts.base import ContractBaseModel
from core.contracts.context import AgentContext, ContextPriority, ContextSectionName


class ContextItemSource(StrEnum):
    """Origin of an engineered context item."""

    AGENT_RULES = "agent_rules"
    REPOSITORY_SUMMARY = "repository_summary"
    REPOSITORY_FILE = "repository_file"
    ARCHITECTURE_SUMMARY = "architecture_summary"
    MEMORY = "memory"
    VECTOR_MEMORY = "vector_memory"
    UPSTREAM = "upstream"


class ContextItem(ContractBaseModel):
    """A candidate context item before final assembly."""

    id: str = Field(min_length=1)
    source: ContextItemSource
    title: str = Field(min_length=1)
    content: str
    priority: ContextPriority = ContextPriority.NORMAL
    token_hint: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextEngineeringConfig(ContractBaseModel):
    """Configuration for context selection, compression, and budgeting."""

    max_token_hint: int = Field(default=6000, ge=1)
    reserved_output_token_hint: int = Field(default=1000, ge=0)
    enable_repository_summary: bool = True
    enable_architecture_summary: bool = True
    enable_memory: bool = True
    enable_compression: bool = True
    repository_file_limit: int = Field(default=200, ge=0)
    selected_repository_file_limit: int = Field(default=12, ge=0)
    repository_file_token_soft_limit: int = Field(default=900, ge=100)
    repository_file_max_bytes: int = Field(default=20_000, ge=1000)
    item_token_soft_limit: int = Field(default=700, ge=100)

    @property
    def context_token_budget(self) -> int:
        """Token hint available for input context."""

        return max(1, self.max_token_hint - self.reserved_output_token_hint)


class ContextEngineeringRequest(ContractBaseModel):
    """Request to build smart context for an agent."""

    agent_name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    agent_context_path: Path
    repository_path: Path | None = None
    architecture_context: str | None = None
    upstream_context: tuple[str, ...] = Field(default_factory=tuple)
    workflow_id: UUID | None = None
    thread_id: str | None = None
    include_sections: tuple[ContextSectionName, ...] | None = None
    exclude_sections: tuple[ContextSectionName, ...] = Field(default_factory=tuple)
    config: ContextEngineeringConfig = Field(default_factory=ContextEngineeringConfig)


class ContextEngineeringResult(ContractBaseModel):
    """Engineered context result for prompt construction."""

    agent_name: str = Field(min_length=1)
    context: AgentContext
    selected_items: tuple[ContextItem, ...] = Field(default_factory=tuple)
    dropped_items: tuple[ContextItem, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    token_hint: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

