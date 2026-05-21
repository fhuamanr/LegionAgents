"""Workflow graph contracts."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact
from core.contracts.execution import AgentExecutionResult


class WorkflowEdge(BaseModel):
    """Directed dependency between two agents."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    condition: str | None = None


class WorkflowDefinition(BaseModel):
    """Declarative workflow topology."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    agents: tuple[str, ...]
    edges: tuple[WorkflowEdge, ...] = Field(default_factory=tuple)


class WorkflowState(BaseModel):
    """Mutable workflow state passed across graph nodes."""

    workflow_id: UUID = Field(default_factory=uuid4)
    task: str = Field(min_length=1)
    active_agent: str | None = None
    statuses: dict[str, AgentStatus] = Field(default_factory=dict)
    results: dict[str, AgentExecutionResult] = Field(default_factory=dict)
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

