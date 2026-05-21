"""Agent execution request and result contracts."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact


class AgentExecutionRequest(BaseModel):
    """Input passed to one agent execution boundary."""

    model_config = ConfigDict(frozen=True)

    execution_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID = Field(default_factory=uuid4)
    agent_name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    upstream_artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionResult(BaseModel):
    """Output returned by one agent execution boundary."""

    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    agent_name: str = Field(min_length=1)
    status: AgentStatus
    summary: str = ""
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    errors: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

