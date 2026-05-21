"""Repository-aware context providers."""

from pathlib import Path

from core.contracts.context import ContextPriority
from core.context_engineering.models import ContextItem, ContextItemSource
from core.context_engineering.summarization import RepositorySummarizer


class RepositorySummaryProvider:
    """Provides repository summaries as context items."""

    def __init__(self, summarizer: RepositorySummarizer | None = None) -> None:
        self._summarizer = summarizer or RepositorySummarizer()

    async def provide(self, repository_path: Path | None) -> tuple[ContextItem, ...]:
        if repository_path is None:
            return tuple()
        summary = await self._summarizer.summarize(repository_path)
        if not summary.strip():
            return tuple()
        return (
            ContextItem(
                id="repository-summary",
                source=ContextItemSource.REPOSITORY_SUMMARY,
                title="Repository Summary",
                content=summary,
                priority=ContextPriority.HIGH,
                token_hint=max(1, len(summary) // 4),
                metadata={"path": str(repository_path)},
            ),
        )

