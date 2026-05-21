"""Story extraction engine."""

from __future__ import annotations

import re

from core.contracts.ingestion import ExtractedEpic, ExtractedStory, ParsedDocument
from core.contracts.outputs import AcceptanceCriterion, UserStory
from core.ingestion.classifiers import KeywordRequirementClassifier, RequirementClassifier


class StoryExtractionEngine:
    """Extracts epics, stories, and acceptance criteria from normalized text."""

    def __init__(self, classifier: RequirementClassifier | None = None) -> None:
        self._classifier = classifier or KeywordRequirementClassifier()

    async def extract(self, document: ParsedDocument) -> tuple[tuple[ExtractedEpic, ...], tuple[ExtractedStory, ...]]:
        """Extract epics and stories from a normalized document."""

        epics = await self._extract_epics(document)
        stories = await self._extract_stories(document, epics)
        return epics, stories

    async def _extract_epics(self, document: ParsedDocument) -> tuple[ExtractedEpic, ...]:
        epics: list[ExtractedEpic] = []
        for index, section in enumerate(document.sections, start=1):
            if "epic" not in section.title.lower():
                continue
            epic_id = self._identifier("EPIC", index, section.title)
            classification = await self._classifier.classify(f"{section.title}\n{section.content}")
            epics.append(
                ExtractedEpic(
                    id=epic_id,
                    title=self._clean_title(section.title),
                    description=section.content or None,
                    classification=classification,
                    metadata={"section_order": section.order},
                )
            )
        return tuple(epics)

    async def _extract_stories(
        self,
        document: ParsedDocument,
        epics: tuple[ExtractedEpic, ...],
    ) -> tuple[ExtractedStory, ...]:
        candidates = self._story_candidates(document)
        extracted: list[ExtractedStory] = []
        for index, candidate in enumerate(candidates, start=1):
            story_id = self._identifier("US", index, candidate["title"])
            criteria = self._acceptance_criteria(candidate["body"], story_id)
            narrative = self._narrative(candidate["body"], candidate["title"])
            classification = await self._classifier.classify(f"{candidate['title']}\n{narrative}")
            extracted.append(
                ExtractedStory(
                    story=UserStory(
                        id=story_id,
                        title=candidate["title"],
                        narrative=narrative,
                        acceptance_criteria=criteria,
                    ),
                    epic_id=self._nearest_epic(candidate["section_order"], epics),
                    source_section=candidate["section_title"],
                    classification=classification,
                    metadata={"section_order": candidate["section_order"]},
                )
            )
        return tuple(extracted)

    def _story_candidates(self, document: ParsedDocument) -> list[dict[str, str | int]]:
        candidates: list[dict[str, str | int]] = []
        for section in document.sections:
            title = self._clean_title(section.title)
            body = section.content
            if self._looks_like_story(title, body):
                candidates.append(
                    {
                        "title": title,
                        "body": body,
                        "section_title": section.title,
                        "section_order": section.order,
                    }
                )
                continue
            candidates.extend(self._inline_story_candidates(section.title, body, section.order))
        if not candidates and self._looks_like_story("", document.text):
            candidates.append(
                {
                    "title": "User Story",
                    "body": document.text,
                    "section_title": "Document",
                    "section_order": 0,
                }
            )
        return candidates

    def _inline_story_candidates(self, section_title: str, body: str, section_order: int) -> list[dict[str, str | int]]:
        pattern = re.compile(
            r"(?im)^(?:[-*]\s*)?(?:story|user story)\s*[:#-]?\s*(?P<title>.+?)\n(?P<body>.*?)(?=^(?:[-*]\s*)?(?:story|user story)\s*[:#-]|\Z)",
            flags=re.DOTALL,
        )
        return [
            {
                "title": self._clean_title(match.group("title")),
                "body": match.group("body").strip(),
                "section_title": section_title,
                "section_order": section_order,
            }
            for match in pattern.finditer(body)
        ]

    def _acceptance_criteria(self, text: str, story_id: str) -> tuple[AcceptanceCriterion, ...]:
        criteria_block = self._criteria_block(text)
        if not criteria_block:
            return tuple()
        lines = [
            re.sub(r"^[-*0-9.)\s]+", "", line).strip()
            for line in criteria_block.splitlines()
            if line.strip()
        ]
        criteria: list[AcceptanceCriterion] = []
        for index, line in enumerate((line for line in lines if line), start=1):
            scenario, expected = self._split_criterion(line)
            criteria.append(
                AcceptanceCriterion(
                    id=f"{story_id}-AC{index}",
                    scenario=scenario,
                    expected_result=expected,
                )
            )
        return tuple(criteria)

    def _criteria_block(self, text: str) -> str:
        pattern = re.compile(
            r"(?is)(?:acceptance criteria|acceptance|criteria)\s*:?\s*(?P<body>.*?)(?=\n\s*(?:notes|dependencies|risks|story|user story)\s*:|\Z)"
        )
        match = pattern.search(text)
        return match.group("body").strip() if match else ""

    def _split_criterion(self, line: str) -> tuple[str, str]:
        if " then " in line.lower():
            before, after = re.split(r"\bthen\b", line, maxsplit=1, flags=re.IGNORECASE)
            return before.strip(" ,."), after.strip(" ,.")
        return line, line

    def _narrative(self, body: str, title: str) -> str:
        match = re.search(r"(?is)(as a .+? so that .+?)(?:\n\s*(?:acceptance criteria|criteria)\s*:|\Z)", body)
        if match:
            return " ".join(match.group(1).split())
        stripped = re.sub(r"(?is)(acceptance criteria|criteria)\s*:.*$", "", body).strip()
        return stripped or title

    def _looks_like_story(self, title: str, body: str) -> bool:
        text = f"{title}\n{body}".lower()
        return "user story" in text or "as a " in text or "acceptance criteria" in text

    def _nearest_epic(self, section_order: int | str, epics: tuple[ExtractedEpic, ...]) -> str | None:
        numeric_order = int(section_order)
        previous_epics = [
            epic for epic in epics if int(epic.metadata.get("section_order", -1)) <= numeric_order
        ]
        return previous_epics[-1].id if previous_epics else (epics[0].id if epics else None)

    def _identifier(self, prefix: str, index: int, title: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").upper()
        slug = slug[:32] or str(index)
        return f"{prefix}-{index:03d}-{slug}"

    def _clean_title(self, title: str) -> str:
        return re.sub(r"(?i)^#+\s*|^(epic|story|user story)\s*[:#-]?\s*", "", title).strip() or title.strip()
