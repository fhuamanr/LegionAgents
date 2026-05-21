"""Context selection and leakage prevention."""

from hashlib import sha256

from core.context_engineering.models import ContextItem


class ContextSelector:
    """Selects and deduplicates candidate context items."""

    async def select(self, items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
        return items


class SmartContextSelector(ContextSelector):
    """Deduplicates context and prevents agent context leakage."""

    async def select(self, items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
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
        return tuple(selected)

    def _fingerprint(self, item: ContextItem) -> str:
        source_path = str(item.metadata.get("path", ""))
        payload = f"{item.source}:{source_path}:{item.content.strip()}"
        return sha256(payload.encode("utf-8")).hexdigest()

    def _leaks_other_agent_context(self, item: ContextItem) -> bool:
        owner = item.metadata.get("agent_name")
        allowed = item.metadata.get("requested_agent")
        return bool(owner and allowed and owner != allowed)

