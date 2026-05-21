import pytest

from core.contracts.ingestion import (
    IngestionSource,
    IngestionSourceType,
    IngestionValidationSeverity,
    RequirementCategory,
)
from core.ingestion import (
    JiraStoryParser,
    StoryIngestionPipeline,
    StoryParserRegistry,
)


@pytest.mark.asyncio
async def test_markdown_ingestion_extracts_epics_stories_and_acceptance_criteria() -> None:
    markdown = """# Epic: Delivery Monitoring

The platform must expose operational delivery visibility.

## User Story: Monitor workflow execution

As a delivery lead, I want to view live agent workflow progress so that I can identify blocked delivery steps.

Acceptance Criteria:
- Given a workflow is running then the dashboard shows the active agent
- Given QA rejects a story then the workflow routes back to Developer
"""

    result = await StoryIngestionPipeline().ingest_text(
        markdown,
        name="stories.md",
        source_type=IngestionSourceType.MARKDOWN,
    )

    assert result.valid is True
    assert len(result.epics) == 1
    assert len(result.stories) == 1
    assert len(result.acceptance_criteria) == 2
    assert result.stories[0].epic_id == result.epics[0].id
    assert result.stories[0].classification.category in {
        RequirementCategory.FUNCTIONAL,
        RequirementCategory.UX,
    }


@pytest.mark.asyncio
async def test_inline_text_ingestion_normalizes_and_warns_when_criteria_missing() -> None:
    result = await StoryIngestionPipeline().ingest_text(
        """Story: Export QA report

As a QA engineer, I want to export the report so that stakeholders can review test evidence.
"""
    )

    assert len(result.stories) == 1
    assert result.valid is True
    assert any(
        issue.severity == IngestionValidationSeverity.WARNING
        and issue.code == "story.missing_acceptance_criteria"
        for issue in result.validation_issues
    )


@pytest.mark.asyncio
async def test_empty_ingestion_result_is_invalid() -> None:
    result = await StoryIngestionPipeline().ingest_text("General notes without story structure.")

    assert result.valid is False
    assert any(issue.code == "stories.empty" for issue in result.validation_issues)


def test_parser_registry_resolves_registered_parser() -> None:
    source = IngestionSource(source_type=IngestionSourceType.JIRA, uri="https://example.atlassian.net/browse/AI-1")
    parser = StoryParserRegistry().resolve(source)

    assert isinstance(parser, JiraStoryParser)


@pytest.mark.asyncio
async def test_future_jira_parser_boundary_is_explicit() -> None:
    source = IngestionSource(source_type=IngestionSourceType.JIRA, uri="https://example.atlassian.net/browse/AI-1")
    parser = StoryParserRegistry().resolve(source)

    with pytest.raises(NotImplementedError):
        await parser.parse(source)
