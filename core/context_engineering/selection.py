"""Context selection and leakage prevention."""

from hashlib import sha256
import re

from core.context_engineering.models import ContextEngineeringRequest, ContextItem, ContextItemSource
from core.contracts.context import ContextPriority


class ContextSelector:
    """Selects and deduplicates candidate context items."""

    async def select(
        self,
        items: tuple[ContextItem, ...],
        request: ContextEngineeringRequest | None = None,
    ) -> tuple[ContextItem, ...]:
        return items


class SmartContextSelector(ContextSelector):
    """Deduplicates context, prevents leakage, and ranks by semantic relevance."""

    async def select(
        self,
        items: tuple[ContextItem, ...],
        request: ContextEngineeringRequest | None = None,
    ) -> tuple[ContextItem, ...]:
        selected: list[ContextItem] = []
        seen: set[str] = set()
        for item in items:
            if self._leaks_other_agent_context(item):
                continue
            fingerprint = self._fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            selected.append(item)
        return tuple(sorted(selected, key=lambda item: self._rank(item, request)))

    def _fingerprint(self, item: ContextItem) -> str:
        source_path = str(item.metadata.get("path", ""))
        payload = f"{item.source}:{source_path}:{item.content.strip()}"
        return sha256(payload.encode("utf-8")).hexdigest()

    def _leaks_other_agent_context(self, item: ContextItem) -> bool:
        owner = item.metadata.get("agent_name")
        allowed = item.metadata.get("requested_agent")
        return bool(owner and allowed and owner != allowed)

    def _rank(
        self,
        item: ContextItem,
        request: ContextEngineeringRequest | None,
    ) -> tuple[int, int, int, str]:
        priority_rank = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.NORMAL: 2,
            ContextPriority.LOW: 3,
        }[item.priority]
        architecture_rank = 0 if item.metadata.get("architecture_context") else 1
        relevance = self._semantic_score(item, request)
        return priority_rank, architecture_rank, -relevance, item.id

    def _semantic_score(
        self,
        item: ContextItem,
        request: ContextEngineeringRequest | None,
    ) -> int:
        if request is None:
            return 0
        query = " ".join(
            part
            for part in (
                request.agent_name,
                request.task,
                request.architecture_context or "",
                " ".join(request.upstream_context),
            )
            if part
        )
        terms = self._terms(query)
        if not terms:
            return 0
        haystack = f"{item.title} {item.content} {item.metadata.get('path', '')}".lower()
        score = sum(1 for term in terms if term in haystack)
        if item.source == ContextItemSource.REPOSITORY_FILE:
            score += int(item.metadata.get("repository_relevance", 0))
        return score

    def _terms(self, text: str) -> set[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "into",
            "must",
            "real",
            "runtime",
            "system",
            "agent",
            "agents",
        }
        return {
            term
            for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
            if term not in stop_words
        }

