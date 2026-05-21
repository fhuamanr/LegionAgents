"""Agent identity and registration contracts."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(StrEnum):
    """Known delivery-platform roles.

    Additional roles can still be loaded dynamically through AgentDefinition.
    This enum captures the first-class roles used by the default workflow.
    """

    BA = "ba"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    QA = "qa"
    DOCS = "docs"
    PR = "pr"


class AgentStatus(StrEnum):
    """Lifecycle status for an agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentDefinition(BaseModel):
    """Runtime definition of an agent and its isolated knowledge root."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str | None = None
    context_path: Path
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    output_contract: str | None = None
    enabled: bool = True

