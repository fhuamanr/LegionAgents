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


@pytest.mark.asyncio
async def test_qa_semantic_aliases_are_mapped_to_structured_fields() -> None:
    validator = PydanticOutputValidator(QAOutput)
    raw = """```json
{
  "agent_name": "qa",
  "summary": "QA checkout validation.",
  "test_results": [
    {"description":"Checkout happy path", "status":"passed"},
    {"description":"Invalid credit card shows generic error", "status":"failed", "evidence":"Expected specific validation message."}
  ],
  "issues_found": [
    "Checkout fails to display detailed invalid card error."
  ],
  "recommendations": [
    "Add explicit credit card validation messaging."
  ],
  "failed_validations": [
    {"title":"Missing card validation", "severity":"high", "evidence":"frontend/src/routes/Checkout.tsx and backend/src/api/routes/checkout.py"}
  ],
  "status": "failed"
}
```"""
    output = await validator.validate(raw, strategy="qa_sections")
    assert output.findings
    assert output.test_reports
    assert output.bug_summaries
    assert output.passed is False
    metadata = output.metadata
    assert isinstance(metadata.get("structured_fix_requests"), list)
    assert metadata["structured_fix_requests"]
    assert isinstance(metadata.get("qa_semantic_extraction_report"), str)
    assert "Structured fix requests generated" in metadata["qa_semantic_extraction_report"]


@pytest.mark.asyncio
async def test_qa_semantic_content_does_not_collapse_to_empty_structures() -> None:
    validator = PydanticOutputValidator(QAOutput)
    raw = '{"summary":"qa","issues_found":["Payment validation failed for expired cards."],"status":"failed"}'
    output = await validator.validate(raw, strategy="qa_sections")
    assert len(output.findings) > 0
