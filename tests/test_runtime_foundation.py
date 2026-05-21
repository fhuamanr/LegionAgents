import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest
from core.runtime import (
    AgentExecutor,
    BaseAgent,
    PydanticOutputValidator,
    RetryEngine,
    RetryPolicy,
    RuntimeAgentConfig,
    RuntimeExecutionContext,
    ToolDefinition,
    ToolRegistry,
)


class ExampleOutput(BaseModel):
    summary: str = Field(min_length=1)
    value: int


class ExampleAgent(BaseAgent[ExampleOutput]):
    def __init__(self, response: str, **kwargs: object) -> None:
        self.calls = 0
        super().__init__(
            config=RuntimeAgentConfig(
                name="example",
                role="example",
                context_path=Path.cwd() / "agents" / "developer",
                output_schema_name="ExampleOutput",
            ),
            output_validator=PydanticOutputValidator(ExampleOutput),
            **kwargs,
        )
        self._response = response
        self.last_context: RuntimeExecutionContext | None = None

    async def invoke(self, context: RuntimeExecutionContext) -> str:
        self.calls += 1
        self.last_context = context
        return self._response


class FlakyAgent(ExampleAgent):
    async def invoke(self, context: RuntimeExecutionContext) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        self.last_context = context
        return self._response


@pytest.mark.asyncio
async def test_base_agent_executes_with_markdown_context_and_validation() -> None:
    agent = ExampleAgent(json.dumps({"summary": "done", "value": 7}))

    result = await agent.execute(
        AgentExecutionRequest(agent_name="example", task="Implement runtime foundation")
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "done"
    assert result.metadata["prompt_message_count"] == 2
    assert result.metadata["context_document_count"] > 0
    assert agent.last_context is not None
    assert "SIEMPRE agregar logging" in agent.last_context.prompt_messages[1].content


@pytest.mark.asyncio
async def test_base_agent_retries_transient_failures() -> None:
    agent = FlakyAgent(
        json.dumps({"summary": "retried", "value": 1}),
        retry_engine=RetryEngine(
            RetryPolicy(max_attempts=2, initial_delay_seconds=0, backoff_multiplier=1)
        ),
    )

    result = await agent.execute(
        AgentExecutionRequest(agent_name="example", task="Retry once")
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "retried"
    assert agent.calls == 2


@pytest.mark.asyncio
async def test_base_agent_returns_failed_result_for_invalid_output() -> None:
    agent = ExampleAgent("not json")

    result = await agent.execute(
        AgentExecutionRequest(agent_name="example", task="Validate output")
    )

    assert result.status == AgentStatus.FAILED
    assert "Output is not valid JSON" in result.errors[0]


@pytest.mark.asyncio
async def test_agent_executor_dispatches_registered_agent() -> None:
    agent = ExampleAgent(json.dumps({"summary": "dispatched", "value": 3}))
    executor = AgentExecutor()
    await executor.register(agent)

    result = await executor.execute(
        AgentExecutionRequest(agent_name="example", task="Dispatch")
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "dispatched"
    assert await executor.list_agents() == ("example",)


@pytest.mark.asyncio
async def test_tool_registry_registers_and_lists_tools() -> None:
    async def handler() -> str:
        return "ok"

    registry = ToolRegistry()
    await registry.register(
        ToolDefinition(
            name="example_tool",
            description="Example async tool.",
            handler=handler,
        )
    )

    assert await registry.names() == ("example_tool",)
    assert await (await registry.get("example_tool")).handler() == "ok"
