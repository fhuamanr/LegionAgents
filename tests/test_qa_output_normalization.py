import pytest

from core.contracts.outputs import QAOutput
from core.runtime.validation import PydanticOutputValidator


@pytest.mark.asyncio
async def test_qa_empty_output_gets_fallback_payload() -> None:
    validator = PydanticOutputValidator(QAOutput)
    output = await validator.validate("", strategy="qa_sections")
    assert output.agent_name == "qa"
    assert output.summary
    assert isinstance(output.findings, tuple)
    assert isinstance(output.test_reports, tuple)
    assert output.metadata.get("status") == "needs_review"


@pytest.mark.asyncio
async def test_qa_partial_output_gets_required_fields() -> None:
    validator = PydanticOutputValidator(QAOutput)
    output = await validator.validate('{"passed": true}', strategy="qa_sections")
    assert output.agent_name == "qa"
    assert output.summary
    assert output.passed is True
