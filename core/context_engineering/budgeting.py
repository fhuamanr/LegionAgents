"""Token budgeting utilities."""

from core.contracts.context import ContextPriority
from core.context_engineering.models import ContextEngineeringConfig, ContextItem


class TokenBudgetManager:
    """Selects context items under a token budget."""

    def fit(
        self,
        items: tuple[ContextItem, ...],
        config: ContextEngineeringConfig,
    ) -> tuple[tuple[ContextItem, ...], tuple[ContextItem, ...]]:
        selected: list[ContextItem] = []
        dropped: list[ContextItem] = []
        total = 0
        for item in sorted(items, key=self._rank):
            if total + item.token_hint <= config.context_token_budget:
                selected.append(item)
                total += item.token_hint
            else:
                dropped.append(item)
        return tuple(selected), tuple(dropped)

    def _rank(self, item: ContextItem) -> tuple[int, int, str]:
        priority_rank = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.NORMAL: 2,
            ContextPriority.LOW: 3,
        }[item.priority]
        return priority_rank, item.token_hint, item.id

