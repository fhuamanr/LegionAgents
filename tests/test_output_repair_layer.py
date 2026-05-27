import pytest

from core.contracts.outputs import DeveloperOutput, DocsOutput, QAOutput
from core.runtime.validation import PydanticOutputValidator


@pytest.mark.asyncio
async def test_repair_layer_handles_missing_comma_json() -> None:
    validator = PydanticOutputValidator(DeveloperOutput)
    raw = (
        '{'
        '"agent_name":"developer"'
        '"summary":"Implementation done",'
        '"code_changes":[{"content":"export const x = 1;"}],'
        '"tests":[]'
        '}'
    )
    output = await validator.validate(raw, strategy="developer_sections")
    assert output.agent_name == "developer"
    assert validator.last_validation_metadata["json_repaired"] is True


@pytest.mark.asyncio
async def test_repair_layer_extracts_markdown_wrapped_json() -> None:
    validator = PydanticOutputValidator(QAOutput)
    raw = """```json
{"agent_name":"qa","summary":"ok","passed":true}
```"""
    output = await validator.validate(raw, strategy="qa_sections")
    assert output.agent_name == "qa"
    assert output.summary == "ok"


@pytest.mark.asyncio
async def test_repair_layer_extracts_prose_plus_json() -> None:
    validator = PydanticOutputValidator(DocsOutput)
    raw = """Here is the structured output:
{"agent_name":"docs","summary":"docs summary","documents":[]}
thanks."""
    output = await validator.validate(raw, strategy="docs_sections")
    assert output.agent_name == "docs"
    assert output.summary == "docs summary"


@pytest.mark.asyncio
async def test_repair_layer_falls_back_to_markdown_parser_when_json_unrecoverable() -> None:
    validator = PydanticOutputValidator(DeveloperOutput)
    raw = """Implementation draft
```tsx
export function ProductList() { return null; }
```"""
    output = await validator.validate(raw, strategy=None)
    assert output.agent_name == "developer"
    assert output.code_changes
    assert validator.last_validation_metadata["artifact_fallback_used"] is True
