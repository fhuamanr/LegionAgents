from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from uuid import uuid4

import pytest

from app.schemas import WorkflowResponse, WorkflowStatus
from app.services.execution_service import ExecutionService
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.outputs import BARequirementsOutput
from core.runtime.agent import BaseAgent
from core.runtime.models import RuntimeAgentConfig
from core.runtime.retry import RetryEngine, RetryPolicy
from core.runtime.validation import PydanticOutputValidator
from core.streaming import ExecutionEvent, ExecutionEventType


class _MinimalAgent(BaseAgent[BARequirementsOutput]):
    async def invoke(self, context):  # type: ignore[override]
        return "not json"

    async def build_artifacts(self, request, output):  # type: ignore[override]
        return tuple()


def _workflow(status: WorkflowStatus = WorkflowStatus.RUNNING, **metadata) -> WorkflowResponse:
    now = datetime.now(timezone.utc)
    return WorkflowResponse(
        workflow_id=uuid4(),
        status=status,
        task="test",
        thread_id="t",
        created_at=now,
        updated_at=now,
        metadata=metadata,
    )


def test_timeline_component_has_scroll_container() -> None:
    path = Path("frontend/features/executions/execution-timeline.tsx")
    text = path.read_text(encoding="utf-8")
    assert "data-testid=\"execution-timeline-scroll\"" in text
    assert "overflow-y-auto" in text
    assert "max-h-[28rem]" in text


def test_workflow_progress_calculation() -> None:
    service = ExecutionService()
    workflow = _workflow()
    events = (
        ExecutionEvent(type=ExecutionEventType.AGENT_COMPLETED, agent_name="ba"),
        ExecutionEvent(type=ExecutionEventType.AGENT_COMPLETED, agent_name="architect"),
    )
    assert service._compute_progress_percent(workflow, events, "developer") == 40.0
    assert service._compute_progress_percent(_workflow(status=WorkflowStatus.COMPLETED), events, None) == 100.0
    assert service._compute_progress_percent(_workflow(workflow_mode="ba_only"), tuple(), "ba") == 50.0


@pytest.mark.asyncio
async def test_validator_extracts_json_and_strips_unknown_metadata() -> None:
    validator = PydanticOutputValidator(BARequirementsOutput)
    raw = """```json
{
  "agent_name":"ba",
  "summary":"ok",
  "user_stories":[
    {
      "id":"US-1",
      "title":"Story",
      "narrative":"As a user...",
      "metadata":{"foo":"bar"},
      "acceptance_criteria":[
        {"id":"AC-1","scenario":"s","expected_result":"e"}
      ]
    }
  ]
}
```"""
    parsed = await validator.validate(raw)
    assert parsed.user_stories[0].id == "US-1"
    assert validator.last_validation_metadata["sanitization_applied"] is True
    assert any("user_stories.0.metadata" in item for item in validator.last_validation_metadata["fields_removed"])


@pytest.mark.asyncio
async def test_validator_limits_ba_story_and_criteria_counts() -> None:
    validator = PydanticOutputValidator(BARequirementsOutput)
    stories = []
    for i in range(7):
        stories.append(
            {
                "id": f"US-{i}",
                "title": "t",
                "narrative": "n",
                "acceptance_criteria": [
                    {"id": f"AC-{i}-{j}", "scenario": "s", "expected_result": "e"} for j in range(6)
                ],
            }
        )
    parsed = await validator.validate(json.dumps({"agent_name": "ba", "summary": "ok", "user_stories": stories}))
    assert len(parsed.user_stories) == 3
    assert all(len(story.acceptance_criteria) <= 3 for story in parsed.user_stories)


@pytest.mark.asyncio
async def test_validator_parses_ba_section_strategy_without_json() -> None:
    validator = PydanticOutputValidator(BARequirementsOutput)
    raw = """
NORMALIZED_REQUIREMENT:
Necesito MVP ecommerce.

USER_STORIES:
1. As a buyer, I want product list, so that I can browse.
   AC:
   - Products are visible
   - Basic filters work
2. As a user, I want account creation, so that I can buy.
   AC:
   - Email/password signup

ASSUMPTIONS:
- No external integrations
- Single region

RISKS:
- Scope creep

DEPENDENCIES:
- Product catalog seed
"""
    parsed = await validator.validate(raw, strategy="ba_sections")
    assert parsed.normalized_requirement
    assert len(parsed.user_stories) >= 1


@pytest.mark.asyncio
async def test_schema_error_classified_and_not_retried() -> None:
    retries = RetryEngine(RetryPolicy(max_attempts=3))
    calls = {"count": 0}

    async def op():
        calls["count"] += 1
        raise ValueError("schema_contract_error: user_stories.0.narrative is required")

    with pytest.raises(RuntimeError):
        await retries.run(op)
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_agent_failure_includes_raw_output_preview() -> None:
    agent = _MinimalAgent(
        config=RuntimeAgentConfig(name="ba", role="business analyst", context_path=Path("agents/ba"), output_schema_name="BARequirementsOutput"),
        output_validator=PydanticOutputValidator(BARequirementsOutput),
    )
    result: AgentExecutionResult = await agent.execute(
        AgentExecutionRequest(
            execution_id=uuid4(),
            workflow_id=uuid4(),
            agent_name="ba",
            task="test",
            metadata={"local_lm_studio_safe_mode": True},
        )
    )
    assert result.status.value == "failed"
    assert result.metadata.get("error_type") in {"json_parse_error", "runtime_error"}
    assert "raw_output_preview" in result.metadata
