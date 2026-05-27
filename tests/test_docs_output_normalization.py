import pytest

from core.contracts.outputs import DocsOutput
from core.runtime.validation import PydanticOutputValidator


@pytest.mark.asyncio
async def test_docs_empty_output_gets_fallback_payload() -> None:
    validator = PydanticOutputValidator(DocsOutput)
    output = await validator.validate("", strategy="docs_sections")
    assert output.agent_name == "docs"
    assert output.summary
    assert isinstance(output.documents, tuple)


@pytest.mark.asyncio
async def test_docs_markdown_output_is_preserved_in_metadata() -> None:
    validator = PydanticOutputValidator(DocsOutput)
    raw = "# API Guide\n\nUse endpoint X."
    output = await validator.validate(raw, strategy="docs_sections")
    assert output.agent_name == "docs"
    assert output.summary
    assert output.metadata.get("documentation_markdown")
