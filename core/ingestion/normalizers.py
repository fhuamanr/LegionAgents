"""Normalization layer for parsed story documents."""

from __future__ import annotations

import re

from core.contracts.ingestion import NormalizedSection, ParsedDocument


class DocumentNormalizer:
    """Normalizes raw document text into predictable sections."""

    async def normalize(self, document: ParsedDocument) -> ParsedDocument:
        """Normalize whitespace and split a document into sections."""

        normalized_text = self._normalize_text(document.text)
        sections = self._sections(normalized_text)
        return document.model_copy(
            update={
                "text": normalized_text,
                "sections": sections,
                "metadata": {**document.metadata, "section_count": len(sections)},
            }
        )

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _sections(self, text: str) -> tuple[NormalizedSection, ...]:
        markdown_sections = self._markdown_sections(text)
        if markdown_sections:
            return markdown_sections
        return self._plain_sections(text)

    def _markdown_sections(self, text: str) -> tuple[NormalizedSection, ...]:
        matches = list(re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE))
        if not matches:
            return tuple()

        sections: list[NormalizedSection] = []
        for order, match in enumerate(matches):
            start = match.end()
            end = matches[order + 1].start() if order + 1 < len(matches) else len(text)
            sections.append(
                NormalizedSection(
                    title=match.group(2).strip(),
                    level=len(match.group(1)),
                    content=text[start:end].strip(),
                    order=order,
                    metadata={"format": "markdown"},
                )
            )
        return tuple(sections)

    def _plain_sections(self, text: str) -> tuple[NormalizedSection, ...]:
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        if not blocks and text:
            blocks = [text]
        sections: list[NormalizedSection] = []
        for order, block in enumerate(blocks):
            lines = block.splitlines()
            title = lines[0].strip("-: ")[:80] or f"Section {order + 1}"
            content = "\n".join(lines[1:]).strip() if len(lines) > 1 else block
            sections.append(
                NormalizedSection(
                    title=title,
                    level=1,
                    content=content,
                    order=order,
                    metadata={"format": "plain"},
                )
            )
        return tuple(sections)
