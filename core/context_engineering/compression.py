"""Context compression strategies."""

from abc import ABC, abstractmethod

from core.context_engineering.models import ContextEngineeringConfig, ContextItem


class ContextCompressor(ABC):
    """Compresses context items before budget selection."""

    @abstractmethod
    async def compress(
        self,
        items: tuple[ContextItem, ...],
        config: ContextEngineeringConfig,
    ) -> tuple[ContextItem, ...]:
        """Return compressed context items."""


class ExtractiveContextCompressor(ContextCompressor):
    """Deterministic extractive compressor for local context engineering."""

    async def compress(
        self,
        items: tuple[ContextItem, ...],
        config: ContextEngineeringConfig,
    ) -> tuple[ContextItem, ...]:
        if not config.enable_compression:
            return items
        return tuple(self._compress_item(item, config.item_token_soft_limit) for item in items)

    def _compress_item(self, item: ContextItem, token_limit: int) -> ContextItem:
        if item.token_hint <= token_limit:
            return item

        paragraphs = [part.strip() for part in item.content.split("\n\n") if part.strip()]
        selected: list[str] = []
        total = 0
        for paragraph in paragraphs:
            hint = self._token_hint(paragraph)
            if selected and total + hint > token_limit:
                break
            selected.append(paragraph)
            total += hint
        content = "\n\n".join(selected) or item.content[: token_limit * 4]
        return item.model_copy(
            update={
                "content": content,
                "token_hint": self._token_hint(content),
                "metadata": {**item.metadata, "compressed": True},
            }
        )

    def _token_hint(self, content: str) -> int:
        return max(1, len(content) // 4)

