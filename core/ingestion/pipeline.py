"""Async ingestion pipeline for user story sources."""

from pathlib import Path

from core.contracts.ingestion import (
    IngestionSource,
    IngestionSourceType,
    ParsedDocument,
    StoryIngestionResult,
)
from core.contracts.outputs import AcceptanceCriterion
from core.ingestion.extractors import StoryExtractionEngine
from core.ingestion.normalizers import DocumentNormalizer
from core.ingestion.parsers import StoryParserRegistry, source_type_from_path
from core.ingestion.validators import StoryStructureValidator


class StoryIngestionPipeline:
    """Coordinates parser, normalization, extraction, validation, and classification."""

    def __init__(
        self,
        parser_registry: StoryParserRegistry | None = None,
        normalizer: DocumentNormalizer | None = None,
        extractor: StoryExtractionEngine | None = None,
        validator: StoryStructureValidator | None = None,
    ) -> None:
        self._parser_registry = parser_registry or StoryParserRegistry()
        self._normalizer = normalizer or DocumentNormalizer()
        self._extractor = extractor or StoryExtractionEngine()
        self._validator = validator or StoryStructureValidator()

    async def ingest_path(
        self,
        path: Path,
        source_type: IngestionSourceType | None = None,
    ) -> StoryIngestionResult:
        """Ingest a local file path."""

        resolved_path = path.resolve()
        source = IngestionSource(
            source_type=source_type or source_type_from_path(resolved_path),
            path=resolved_path,
            name=resolved_path.name,
        )
        return await self.ingest(source)

    async def ingest_text(
        self,
        text: str,
        name: str = "inline.txt",
        source_type: IngestionSourceType = IngestionSourceType.TEXT,
    ) -> StoryIngestionResult:
        """Ingest inline text without a file-backed parser."""

        source = IngestionSource(source_type=source_type, name=name, metadata={"inline": True})
        document = await self._normalizer.normalize(
            parsed_document(source=source, text=text, parser_name="InlineTextParser")
        )
        return await self._result_from_document(document)

    async def ingest(self, source: IngestionSource) -> StoryIngestionResult:
        """Ingest any registered source."""

        parser = self._parser_registry.resolve(source)
        parsed = await parser.parse(source)
        document = await self._normalizer.normalize(parsed)
        return await self._result_from_document(document)

    async def _result_from_document(self, document: ParsedDocument) -> StoryIngestionResult:
        epics, stories = await self._extractor.extract(document)
        issues = await self._validator.validate(epics, stories)
        criteria: list[AcceptanceCriterion] = []
        for extracted in stories:
            criteria.extend(extracted.story.acceptance_criteria)
        return StoryIngestionResult(
            source=document.source,
            epics=epics,
            stories=stories,
            acceptance_criteria=tuple(criteria),
            validation_issues=issues,
            metadata={
                "parser": document.metadata.get("parser"),
                "section_count": document.metadata.get("section_count", 0),
                "story_count": len(stories),
                "epic_count": len(epics),
                "acceptance_criteria_count": len(criteria),
            },
        )


def parsed_document(source: IngestionSource, text: str, parser_name: str) -> ParsedDocument:
    """Create a parsed document without importing the model at call sites."""

    return ParsedDocument(source=source, text=text, metadata={"parser": parser_name})
