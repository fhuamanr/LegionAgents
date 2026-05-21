"""Runtime agent executor."""

import logging
from typing import Any

from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.runtime.agent import BaseAgent


class AgentExecutor:
    """Executes registered agents by name.

    The signature is compatible with LangGraph node delegation because it
    accepts an AgentExecutionRequest and returns an AgentExecutionResult.
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent[Any]] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._agents = agents or {}
        self._logger = logger or logging.getLogger(__name__)

    async def register(self, agent: BaseAgent[Any]) -> None:
        if agent.config.name in self._agents:
            raise ValueError(f"Agent already registered: {agent.config.name}")
        self._agents[agent.config.name] = agent

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        agent = self._agents.get(request.agent_name)
        if agent is None:
            self._logger.warning(
                "agent_not_registered",
                extra={"agent_name": request.agent_name},
            )
            return AgentExecutionResult(
                execution_id=request.execution_id,
                agent_name=request.agent_name,
                status=AgentStatus.FAILED,
                errors=(f"Agent not registered: {request.agent_name}",),
            )
        return await agent.execute(request)

    async def list_agents(self) -> tuple[str, ...]:
        return tuple(sorted(self._agents))
