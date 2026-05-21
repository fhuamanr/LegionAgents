"""Prompt composition contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.artifacts import Artifact
from core.contracts.context import AgentContext


class PromptRole(StrEnum):
    """LLM message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class PromptMessage(BaseModel):
    """A composable chat message."""

    model_config = ConfigDict(frozen=True)

    role: PromptRole
    content: str = Field(min_length=1)


class PromptBuildRequest(BaseModel):
    """Input for building an agent prompt."""

    model_config = ConfigDict(frozen=True)

    agent_name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    context: AgentContext
    upstream_artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    output_contract: str | None = None
    additional_instructions: tuple[str, ...] = Field(default_factory=tuple)

