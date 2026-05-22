import json
from pathlib import Path

import pytest

from core.agents.qa import QAAgentRuntime
from core.agents.qa.contracts import QARuntimeConfig
from core.agents.qa.output_contracts import build_qa_output_contract
from core.agents.qa.telemetry import QATelemetryHook
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
            raise RuntimeError("temporary qa model failure")
        return self.response


class RecordingTelemetryHook(QATelemetryHook):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event_name: str, attributes: dict[str, object]) -> None:
        self.events.append(event_name)


def build_runtime(model_client: AgentModelClient) -> QAAgentRuntime:
    return QAAgentRuntime(
        config=QARuntimeConfig(
            context_path=Path.cwd() / "agents" / "qa",
            repository_path=Path.cwd(),
            output_contract=build_qa_output_contract(),
        ),
        model_client=model_client,
    )


@pytest.mark.asyncio
async def test_qa_runtime_returns_structured_report_and_rejection_route() -> None:
    response = json.dumps(
        {
            "agent_name": "qa",
            "summary": "QA found one high severity issue.",
            "passed": False,
            "findings": [
                {
                    "id": "QA-1",
                    "title": "Login failure",
                    "severity": "high",
                    "evidence": "Login flow is broken.",
                }
            ],
            "test_reports": [
                {
                    "name": "Unit tests",
                    "test_type": "unit",
                    "passed": 12,
                    "failed": 1,
                    "command": "pytest",
                }
            ],
            "execution_logs": [
                {"message": "Executed QA validation.", "level": "info", "source": "qa"}
            ],
            "bug_summaries": [
                {
                    "id": "BUG-1",
                    "title": "Login failure",
                    "severity": "high",
                    "reproduction_steps": ["Open login", "Submit valid credentials"],
                    "expected": "User lands on dashboard",
                    "actual": "Error is shown",
                }
            ],
            "coverage": {"lines": 82.5, "branches": 70.0},
        }
    )
    model_client = FakeModelClient(response=response)
    runtime = build_runtime(model_client)

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_name="qa",
            task="Validate developer output",
            metadata={
                "acceptance_criteria": "User can log in.",
                "implementation_context": "Developer changed login flow.",
            },
        )
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "QA found one high severity issue."
    assert result.metadata["route_signal"] == "reject"
    assert result.metadata["structured_output"]["test_reports"][0]["failed"] == 1
    assert result.metadata["structured_output"]["execution_logs"]
    assert set(result.metadata["loaded_rule_files"]) == {
        "gravity.md",
        "anti-gravity.md",
        "severity-rules.md",
        "test-strategy.md",
    }
    assert "SIEMPRE generar pruebas negativas" in model_client.messages[1].content
    assert "severity-rules.md" in model_client.messages[1].content
    assert "User can log in." in model_client.messages[1].content


@pytest.mark.asyncio
async def test_qa_runtime_fails_when_model_output_is_not_json() -> None:
    runtime = build_runtime(FakeModelClient(response="not json"))

    result = await runtime.execute(
        AgentExecutionRequest(agent_name="qa", task="Validate output")
    )

    assert result.status == AgentStatus.FAILED
    assert "not valid JSON" in result.errors[0]


@pytest.mark.asyncio
async def test_qa_runtime_rejects_other_agent_requests() -> None:
    runtime = build_runtime(FakeModelClient(response="{}"))

    result = await runtime.execute(
        AgentExecutionRequest(agent_name="developer", task="Implement feature")
    )

    assert result.status == AgentStatus.FAILED
    assert "cannot execute request for agent" in result.errors[0]


@pytest.mark.asyncio
async def test_qa_runtime_retries_model_invocation_and_emits_telemetry() -> None:
    response = json.dumps(
        {
            "agent_name": "qa",
            "summary": "QA passed after retry.",
            "passed": True,
            "findings": [],
            "test_reports": [],
        }
    )
    telemetry = RecordingTelemetryHook()
    model_client = FlakyModelClient(response=response)
    runtime = QAAgentRuntime(
        config=QARuntimeConfig(
            context_path=Path.cwd() / "agents" / "qa",
            repository_path=Path.cwd(),
            output_contract=build_qa_output_contract(),
        ),
        model_client=model_client,
        telemetry_hook=telemetry,
    )

    result = await runtime.execute(
        AgentExecutionRequest(agent_name="qa", task="Validate retry behavior")
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.metadata["route_signal"] == "continue"
    assert model_client.calls == 2
    assert telemetry.events == [
        "qa_agent_execution_started",
        "qa_agent_execution_completed",
    ]
