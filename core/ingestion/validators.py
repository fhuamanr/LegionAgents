"""Validation for ingested stories."""

from core.contracts.ingestion import (
    ExtractedEpic,
    ExtractedStory,
    IngestionValidationIssue,
    IngestionValidationSeverity,
)


class StoryStructureValidator:
    """Validates normalized story structures before workflow execution."""

    async def validate(
        self,
        epics: tuple[ExtractedEpic, ...],
        stories: tuple[ExtractedStory, ...],
    ) -> tuple[IngestionValidationIssue, ...]:
        """Validate epics and stories."""

        issues: list[IngestionValidationIssue] = []
        if not stories:
            issues.append(
                IngestionValidationIssue(
                    severity=IngestionValidationSeverity.ERROR,
                    code="stories.empty",
                    message="No user stories were extracted from the source.",
                )
            )

        known_epics = {epic.id for epic in epics}
        seen_story_ids: set[str] = set()
        for extracted in stories:
            story = extracted.story
            if story.id in seen_story_ids:
                issues.append(
                    IngestionValidationIssue(
                        severity=IngestionValidationSeverity.ERROR,
                        code="story.duplicate_id",
                        message=f"Duplicate story id detected: {story.id}",
                        story_id=story.id,
                    )
                )
            seen_story_ids.add(story.id)

            if len(story.narrative.strip()) < 10:
                issues.append(
                    IngestionValidationIssue(
                        severity=IngestionValidationSeverity.WARNING,
                        code="story.short_narrative",
                        message="Story narrative is unusually short.",
                        story_id=story.id,
                    )
                )
            if not story.acceptance_criteria:
                issues.append(
                    IngestionValidationIssue(
                        severity=IngestionValidationSeverity.WARNING,
                        code="story.missing_acceptance_criteria",
                        message="Story has no acceptance criteria.",
                        story_id=story.id,
                    )
                )
            if extracted.epic_id and extracted.epic_id not in known_epics:
                issues.append(
                    IngestionValidationIssue(
                        severity=IngestionValidationSeverity.ERROR,
                        code="story.unknown_epic",
                        message=f"Story references unknown epic: {extracted.epic_id}",
                        story_id=story.id,
                    )
                )
        return tuple(issues)
