"""Parser boundaries and built-in file parsers for story ingestion."""

from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Iterable
from zipfile import ZipFile
from xml.etree import ElementTree

from core.contracts.ingestion import IngestionSource, IngestionSourceType, ParsedDocument


class StoryParser(ABC):
    """Parser boundary for ingestion sources."""

    supported_source_types: tuple[IngestionSourceType, ...] = tuple()

    def supports(self, source: IngestionSource) -> bool:
        """Return whether this parser supports a source."""

        return source.source_type in self.supported_source_types

    @abstractmethod
    async def parse(self, source: IngestionSource) -> ParsedDocument:
        """Parse a source into document text."""


class TextStoryParser(StoryParser):
    """Plain text story parser."""

    supported_source_types = (IngestionSourceType.TEXT,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        path = _require_path(source)
        return ParsedDocument(
            source=source,
            text=path.read_text(encoding="utf-8"),
            metadata={"parser": self.__class__.__name__},
        )


class MarkdownStoryParser(StoryParser):
    """Markdown story parser."""

    supported_source_types = (IngestionSourceType.MARKDOWN,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        path = _require_path(source)
        return ParsedDocument(
            source=source,
            text=path.read_text(encoding="utf-8"),
            metadata={"parser": self.__class__.__name__},
        )


class DocxStoryParser(StoryParser):
    """DOCX parser using the standard OOXML package layout."""

    supported_source_types = (IngestionSourceType.DOCX,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        path = _require_path(source)
        with ZipFile(path) as package:
            xml = package.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
            if text:
                paragraphs.append(text)
        return ParsedDocument(
            source=source,
            text="\n".join(paragraphs),
            metadata={"parser": self.__class__.__name__, "paragraph_count": len(paragraphs)},
        )


class PdfStoryParser(StoryParser):
    """PDF parser with optional pypdf support and a conservative fallback."""

    supported_source_types = (IngestionSourceType.PDF,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        path = _require_path(source)
        text = self._extract_with_pypdf(path) or self._extract_printable_text(path)
        return ParsedDocument(
            source=source,
            text=text,
            metadata={"parser": self.__class__.__name__, "fallback": "pypdf_unavailable_or_empty"},
        )

    def _extract_with_pypdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except ImportError:
            return ""

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

    def _extract_printable_text(self, path: Path) -> str:
        data = path.read_bytes()
        decoded = data.decode("latin-1", errors="ignore")
        chunks = re.findall(r"[\x20-\x7E]{5,}", decoded)
        return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())


class JiraStoryParser(StoryParser):
    """Future parser boundary for Jira ingestion."""

    supported_source_types = (IngestionSourceType.JIRA,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        raise NotImplementedError("Jira ingestion requires a future Jira adapter.")


class NotionStoryParser(StoryParser):
    """Future parser boundary for Notion ingestion."""

    supported_source_types = (IngestionSourceType.NOTION,)

    async def parse(self, source: IngestionSource) -> ParsedDocument:
        raise NotImplementedError("Notion ingestion requires a future Notion adapter.")


class StoryParserRegistry:
    """Registry that resolves parsers by source type."""

    def __init__(self, parsers: Iterable[StoryParser] | None = None) -> None:
        self._parsers: list[StoryParser] = list(parsers or default_parsers())

    def register(self, parser: StoryParser) -> None:
        """Register a parser implementation."""

        self._parsers.append(parser)

    def resolve(self, source: IngestionSource) -> StoryParser:
        """Resolve a parser for a source."""

        for parser in self._parsers:
            if parser.supports(source):
                return parser
        raise ValueError(f"No parser registered for source type: {source.source_type}")


def default_parsers() -> tuple[StoryParser, ...]:
    """Default parser implementations."""

    return (
        MarkdownStoryParser(),
        TextStoryParser(),
        DocxStoryParser(),
        PdfStoryParser(),
        JiraStoryParser(),
        NotionStoryParser(),
    )


def source_type_from_path(path: Path) -> IngestionSourceType:
    """Infer source type from a local path suffix."""

    suffix = path.suffix.lower()
    mapping = {
        ".md": IngestionSourceType.MARKDOWN,
        ".markdown": IngestionSourceType.MARKDOWN,
        ".txt": IngestionSourceType.TEXT,
        ".docx": IngestionSourceType.DOCX,
        ".pdf": IngestionSourceType.PDF,
    }
    if suffix not in mapping:
        raise ValueError(f"Unsupported story source extension: {suffix}")
    return mapping[suffix]


def _require_path(source: IngestionSource) -> Path:
    if source.path is None:
        raise ValueError(f"Local path is required for {source.source_type} ingestion.")
    if not source.path.exists():
        raise FileNotFoundError(source.path)
    return source.path
