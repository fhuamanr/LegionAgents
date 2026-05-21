"""Agent and workflow state models."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.agents import AgentStatus
from core.contracts.artifacts import Artifact
from core.contracts.base import MutableContractBaseModel, TraceMetadata
from core.contracts.outputs import AgentStructuredOutput


class AgentPhase(StrEnum):
    """Execution phase for a specialized agent."""

    CREATED = "created"
    CONTEXT_LOADING = "context_loading"
    PROMPT_BUILDING = "prompt_building"
    EXECUTING = "executing"
    VALIDATING_OUTPUT = "validating_output"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStateSnapshot(MutableContractBaseModel):
    """State snapshot for one agent in a workflow."""

    agent_name: str = Field(min_length=1)
    status: AgentStatus = AgentStatus.PENDING
    phase: AgentPhase = AgentPhase.CREATED
    attempt: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    input_artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    output_artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    structured_output: AgentStructuredOutput | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTransition(MutableContractBaseModel):
    """State transition emitted during agent execution."""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str = Field(min_length=1)
    from_phase: AgentPhase
    to_phase: AgentPhase
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionState(MutableContractBaseModel):
    """Aggregate state for a multi-agent workflow execution."""

    workflow_id: UUID = Field(default_factory=uuid4)
    task: str = Field(min_length=1)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    active_agent: str | None = None
    agent_states: dict[str, AgentStateSnapshot] = Field(default_factory=dict)
    transitions: tuple[AgentTransition, ...] = Field(default_factory=tuple)
    artifacts: tuple[Artifact, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

