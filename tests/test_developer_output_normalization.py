import json
from pathlib import Path

import pytest

from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest
from core.contracts.outputs import DeveloperOutput
from core.runtime.agent import BaseAgent
from core.runtime.models import RuntimeAgentConfig, RuntimeExecutionContext
from core.runtime.validation import PydanticOutputValidator


@pytest.mark.asyncio
async def test_developer_output_with_content_only_is_normalized() -> None:
    validator = PydanticOutputValidator(DeveloperOutput)
    output = await validator.validate(
        json.dumps(
            {
                "code_changes": [{"content": "export function ProductList() { return null; }"}],
                "tests": [{"content": "test('renders', () => expect(true).toBe(true));"}],
            }
        ),
        strategy="developer_sections",
    )
    assert output.agent_name == "developer"
    assert output.summary
    assert output.code_changes[0].path
    assert output.code_changes[0].change_type == "create"
    assert output.code_changes[0].description
    assert output.tests[0].path
    assert output.tests[0].test_type == "unit"
    assert output.tests[0].description


@pytest.mark.asyncio
async def test_developer_missing_path_defaults_to_generated_file() -> None:
    validator = PydanticOutputValidator(DeveloperOutput)
    output = await validator.validate(
        json.dumps({"code_changes": [{"content": "plain implementation text"}], "tests": [{"content": "plain test notes"}]}),
        strategy="developer_sections",
    )
    assert output.code_changes[0].path == "generated/0.tsx"
    assert output.tests[0].path == "generated/0.test.tsx"


@pytest.mark.asyncio
async def test_developer_markdown_output_parses_into_structured_changes() -> None:
    validator = PydanticOutputValidator(DeveloperOutput)
    raw = """File: src/components/ProductList.tsx
```tsx
export function ProductList() { return null; }
```
File: src/components/ProductList.test.tsx
```ts
test('renders', () => expect(true).toBe(true));
```"""
    output = await validator.validate(raw, strategy="developer_sections")
    assert output.code_changes
    assert output.tests
    assert output.code_changes[0].path == "src/components/ProductList.tsx"
    assert output.tests[0].path == "src/components/ProductList.test.tsx"


class _DeveloperNeedsReviewAgent(BaseAgent[DeveloperOutput]):
    def __init__(self) -> None:
        super().__init__(
            config=RuntimeAgentConfig(
                name="developer",
                role="developer",
                context_path=Path.cwd() / "agents" / "developer",
                output_schema_name="DeveloperOutput",
            ),
            output_validator=PydanticOutputValidator(DeveloperOutput),
        )
        self.calls = 0

    async def invoke(self, context: RuntimeExecutionContext) -> str:
        self.calls += 1
        return "implementation draft without strict json"


@pytest.mark.asyncio
async def test_developer_useful_non_json_output_does_not_fail_hard() -> None:
    agent = _DeveloperNeedsReviewAgent()
    result = await agent.execute(AgentExecutionRequest(agent_name="developer", task="Implement feature"))
    assert result.status == AgentStatus.COMPLETED
    assert result.errors == ()
    assert any(artifact.name == "raw_output.md" for artifact in result.artifacts)
    assert agent.calls == 1
