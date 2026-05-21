"""Retry policies and engines."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

TResult = TypeVar("TResult")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry settings for runtime execution."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.1
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


class RetryEngine:
    """Async retry engine with exponential backoff."""

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self._policy = policy or RetryPolicy()

    async def run(self, operation: Callable[[], Awaitable[TResult]]) -> TResult:
        attempt = 0
        delay = self._policy.initial_delay_seconds
        while True:
            attempt += 1
            try:
                return await operation()
            except self._policy.retryable_exceptions:
                if attempt >= self._policy.max_attempts:
                    raise
                await asyncio.sleep(delay)
                delay *= self._policy.backoff_multiplier

