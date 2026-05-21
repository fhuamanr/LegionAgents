import json
from pathlib import Path

import pytest

from core.agents.developer import DeveloperAgentRuntime
from core.agents.developer.contracts import DeveloperRuntimeConfig
from core.agents.developer.output_contracts import build_developer_output_contract
from core.agents.developer.telemetry import DeveloperTelemetryHook
from core.agents.runtime import AgentModelClient
from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompts import PromptMessage


class FakeModelClient(AgentModelClient):
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: tuple[PromptMessage, ...] = tuple()

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        self.messages = messages
        return self.response


class FlakyModelClient(AgentModelClient):
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary model failure")
        return self.response


class RecordingTelemetryHook(DeveloperTelemetryHook):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event_name: str, attributes: dict[str, object]) -> None:
        self.events.append(event_name)


def build_runtime(model_client: AgentModelClient) -> DeveloperAgentRuntime:
    return DeveloperAgentRuntime(
        config=DeveloperRuntimeConfig(
            context_path=Path.cwd() / "agents" / "developer",
            repository_path=Path.cwd(),
            output_contract=build_developer_output_contract(),
        ),
        model_client=model_client,
    )


@pytest.mark.asyncio
async def test_developer_runtime_returns_structured_execution_result() -> None:
    response = json.dumps(
        {
            "agent_name": "developer",
            "summary": "Prepared implementation work items.",
            "work_items": [
                {
                    "id": "DEV-1",
                    "title": "Create runtime",
                    "description": "Implement the developer runtime boundary.",
                    "target_paths": ["core/agents/developer/runtime.py"],
                    "test_expectations": ["Runtime returns AgentExecutionResult."],
                }
            ],
            "code_changes": [
                {
                    "path": "core/agents/developer/runtime.py",
                    "change_type": "modify",
                    "description": "Make runtime executable.",
                }
            ],
            "tests": [
                {
                    "path": "tests/test_developer_agent_runtime.py",
                    "test_type": "unit",
                    "description": "Validate developer runtime.",
                }
            ],
            "refactoring_suggestions": [
                {
                    "target_path": "core/agents/developer/runtime.py",
                    "rationale": "Keep execution concerns modular.",
                }
            ],
            "commit_message": "feat: add executable developer runtime",
            "pr_draft": {
                "title": "Add executable developer runtime",
                "description": "Introduces developer runtime execution infrastructure.",
                "checklist": ["Tests added"],
            },
        }
    )
    model_client = FakeModelClient(response=response)
    runtime = build_runtime(model_client)

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_name="developer",
            task="Generate developer agent runtime",
            metadata={
                "architecture_context": "Use Clean Architecture boundaries.",
                "ba_stories": "As a user, I need executable developer outputs.",
            },
        )
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "Prepared implementation work items."
    assert result.artifacts[-1].producer_agent == "developer"
    assert result.metadata["prompt_message_count"] == 2
    assert result.metadata["repository_analysis"]["detected_languages"]
    assert "SIEMPRE agregar logging" in model_client.messages[1].content
    assert "Use Clean Architecture boundaries." in model_client.messages[1].content
    assert "As a user, I need executable developer outputs." in model_client.messages[1].content
    assert "core/agents/developer/runtime.py" in model_client.messages[1].content
    assert set(result.metadata["loaded_rule_files"]) == {
        "gravity.md",
        "anti-gravity.md",
        "coding-standards.md",
        "architecture.md",
        "forbidden.md",
        "naming.md",
        "testing.md",
        "security.md",
    }
    assert "anti-gravity.md" in model_client.messages[1].content


@pytest.mark.asyncio
async def test_developer_runtime_fails_when_model_output_is_not_json() -> None:
    runtime = build_runtime(FakeModelClient(response="not json"))

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_name="developer",
            task="Generate developer agent runtime",
        )
    )

    assert result.status == AgentStatus.FAILED
    assert "not valid JSON" in result.errors[0]


@pytest.mark.asyncio
async def test_developer_runtime_rejects_other_agent_requests() -> None:
    runtime = build_runtime(FakeModelClient(response="{}"))

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_name="qa",
            task="Validate implementation",
        )
    )

    assert result.status == AgentStatus.FAILED
    assert "cannot execute request for agent" in result.errors[0]


@pytest.mark.asyncio
async def test_developer_runtime_retries_model_invocation_and_emits_telemetry() -> None:
    response = json.dumps(
        {
            "agent_name": "developer",
            "summary": "Recovered after retry.",
            "work_items": [],
        }
    )
    telemetry = RecordingTelemetryHook()
    model_client = FlakyModelClient(response=response)
    runtime = DeveloperAgentRuntime(
        config=DeveloperRuntimeConfig(
            context_path=Path.cwd() / "agents" / "developer",
            repository_path=Path.cwd(),
            output_contract=build_developer_output_contract(),
        ),
        model_client=model_client,
        telemetry_hook=telemetry,
    )

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_name="developer",
            task="Generate developer agent runtime",
        )
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "Recovered after retry."
    assert model_client.calls == 2
    assert telemetry.events == [
        "developer_agent_execution_started",
        "developer_agent_execution_completed",
    ]
