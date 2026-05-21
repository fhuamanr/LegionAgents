"""Runtime foundation models."""

from pathlib import Path
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel
from core.contracts.context import AgentContext
from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompts import PromptMessage


class RuntimeAgentConfig(ContractBaseModel):
    """Dependency-injection friendly configuration for one runtime agent."""

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    context_path: Path
    output_schema_name: str = Field(default="structured_output", min_length=1)
    max_context_token_hint: int | None = Field(default=None, ge=1)
    system_instructions: tuple[str, ...] = Field(default_factory=tuple)
    additional_instructions: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeExecutionContext(ContractBaseModel):
    """Isolated runtime context for one agent execution."""

    request: AgentExecutionRequest
    agent_config: RuntimeAgentConfig
    agent_context: AgentContext
    prompt_messages: tuple[PromptMessage, ...] = Field(default_factory=tuple)
    tools: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

