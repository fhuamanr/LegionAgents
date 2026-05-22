"""Workflow agent runtime factory."""

from __future__ import annotations

from pathlib import Path

from core.agents.llm_runtime import LLMStructuredAgentRuntime, build_llm_agent_runtimes
from core.agents.runtime import AgentModelClient


def build_default_agent_runtimes(
    *,
    project_root: Path | None = None,
    model_client: AgentModelClient | None = None,
) -> dict[str, LLMStructuredAgentRuntime]:
    """Return real LLM-backed runtimes for the default delivery workflow."""

    return build_llm_agent_runtimes(project_root=project_root, model_client=model_client)
