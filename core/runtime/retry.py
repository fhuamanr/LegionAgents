"""Retry policies and engines."""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

TResult = TypeVar("TResult")

Classification = Literal[
    "retryable",
    "non_retryable",
    "retryable_after_compression",
    "retryable_after_manual_action",
]


class ContextWindowExceededError(ValueError):
    """Raised when an LLM prompt exceeds provider context limits."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry settings for runtime execution."""

    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 3.0
    jitter_seconds: float = 0.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


@dataclass(frozen=True, slots=True)
class ProviderErrorDecision:
    classification: Classification
    retry_allowed: bool
    compression_allowed: bool
    user_message: str
    technical_message: str
    suggested_action: str
    error_type: str


@dataclass(frozen=True, slots=True)
class RetryDecisionEvent:
    event_type: str
    attempt: int
    max_attempts: int
    classification: Classification
    retry_allowed: bool
    compression_allowed: bool
    user_message: str
    technical_message: str
    suggested_action: str
    error_type: str


class ProviderErrorClassifier:
    """Classifies provider/runtime errors into retry buckets."""

    _context_patterns = (
        "context size has been exceeded",
        "context length exceeded",
        "maximum context length",
        "request too large",
        "prompt too large",
        "n_ctx",
        "n_keep",
        "exceeds the available context size",
        "context window",
    )
    _auth_patterns = ("invalid api key", "unauthorized", "forbidden", "authentication failed")
    _model_patterns = ("model not found", "model not loaded", "no model loaded")
    _unsupported_patterns = (
        "unsupported response_format",
        "invalid request",
        "malformed",
        "missing provider configuration",
        "prompt too large",
    )
    _transient_patterns = ("timeout", "timed out", "connection reset", "temporary", "overloaded", "temporarily unavailable")
    _output_validation_patterns = ("schema_contract_error", "json_parse_error", "output validation failed")

    def classify(self, exc: Exception) -> ProviderErrorDecision:
        text = str(exc)
        lowered = text.lower()
        status_code = _extract_status_code(text)
        error_type = type(exc).__name__

        if isinstance(exc, ContextWindowExceededError) or any(pattern in lowered for pattern in self._context_patterns):
            return ProviderErrorDecision(
                classification="retryable_after_compression",
                retry_allowed=False,
                compression_allowed=True,
                user_message="The selected model context window is too small for this workflow.",
                technical_message=text,
                suggested_action="Use compact mode, reduce context, increase model context, or choose a larger model.",
                error_type=error_type,
            )
        if any(pattern in lowered for pattern in self._output_validation_patterns):
            return ProviderErrorDecision(
                classification="non_retryable",
                retry_allowed=False,
                compression_allowed=False,
                user_message="Agent output validation failed.",
                technical_message=text,
                suggested_action="Repair JSON/contract output locally or tighten output contract instructions.",
                error_type=error_type,
            )
        if any(pattern in lowered for pattern in self._auth_patterns) or status_code in {401, 403}:
            return ProviderErrorDecision(
                classification="non_retryable",
                retry_allowed=False,
                compression_allowed=False,
                user_message="Provider authentication failed.",
                technical_message=text,
                suggested_action="Check API key and provider credentials.",
                error_type=error_type,
            )
        if (
            any(pattern in lowered for pattern in self._model_patterns)
            or "model unloaded" in lowered
            or "no models loaded" in lowered
            or status_code == 404
        ):
            return ProviderErrorDecision(
                classification="retryable_after_manual_action",
                retry_allowed=False,
                compression_allowed=False,
                user_message="The configured model is not available.",
                technical_message=text,
                suggested_action="Load/select a valid model, then test the provider again.",
                error_type=error_type,
            )
        if any(pattern in lowered for pattern in self._unsupported_patterns) or status_code in {400, 422}:
            return ProviderErrorDecision(
                classification="non_retryable",
                retry_allowed=False,
                compression_allowed=False,
                user_message="Provider request/configuration is invalid.",
                technical_message=text,
                suggested_action="Review provider settings and request payload compatibility.",
                error_type=error_type,
            )
        if status_code == 429 or (status_code is not None and 500 <= status_code <= 599) or any(pattern in lowered for pattern in self._transient_patterns):
            return ProviderErrorDecision(
                classification="retryable",
                retry_allowed=True,
                compression_allowed=False,
                user_message="Temporary provider/network issue detected. Retrying automatically.",
                technical_message=text,
                suggested_action="Retrying automatically with backoff.",
                error_type=error_type,
            )
        return ProviderErrorDecision(
            classification="non_retryable",
            retry_allowed=False,
            compression_allowed=False,
            user_message="Provider execution failed.",
            technical_message=text,
            suggested_action="Review provider/runtime configuration and logs.",
            error_type=error_type,
        )


class RetryEngine:
    """Async retry engine with classifier-based decisions and exponential backoff."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        classifier: ProviderErrorClassifier | None = None,
    ) -> None:
        self._policy = policy or RetryPolicy()
        self._classifier = classifier or ProviderErrorClassifier()

    async def run(
        self,
        operation: Callable[[], Awaitable[TResult]],
        *,
        on_compression_retry: Callable[[Exception], Awaitable[bool] | bool] | None = None,
        on_decision: Callable[[RetryDecisionEvent], Awaitable[None] | None] | None = None,
    ) -> TResult:
        attempt = 0
        delay = self._policy.initial_delay_seconds
        compression_used = False
        while True:
            attempt += 1
            try:
                return await operation()
            except self._policy.retryable_exceptions as exc:
                decision = self._classifier.classify(exc)
                await _emit_decision(
                    on_decision,
                    RetryDecisionEvent(
                        event_type="provider_error_classified",
                        attempt=attempt,
                        max_attempts=self._policy.max_attempts,
                        classification=decision.classification,
                        retry_allowed=decision.retry_allowed,
                        compression_allowed=decision.compression_allowed,
                        user_message=decision.user_message,
                        technical_message=decision.technical_message,
                        suggested_action=decision.suggested_action,
                        error_type=decision.error_type,
                    ),
                )
                if decision.compression_allowed and on_compression_retry is not None and not compression_used:
                    compression_used = True
                    await _emit_decision(
                        on_decision,
                        RetryDecisionEvent(
                            event_type="compression_retry_started",
                            attempt=attempt,
                            max_attempts=self._policy.max_attempts,
                            classification=decision.classification,
                            retry_allowed=False,
                            compression_allowed=True,
                            user_message=decision.user_message,
                            technical_message=decision.technical_message,
                            suggested_action=decision.suggested_action,
                            error_type=decision.error_type,
                        ),
                    )
                    compressed = await _maybe_await(on_compression_retry(exc))
                    if compressed:
                        await _emit_decision(
                            on_decision,
                            RetryDecisionEvent(
                                event_type="retry_started",
                                attempt=attempt + 1,
                                max_attempts=self._policy.max_attempts,
                                classification=decision.classification,
                                retry_allowed=True,
                                compression_allowed=False,
                                user_message=decision.user_message,
                                technical_message=decision.technical_message,
                                suggested_action="Retrying once with compressed prompt.",
                                error_type=decision.error_type,
                            ),
                        )
                        continue
                    await _emit_decision(
                        on_decision,
                        RetryDecisionEvent(
                            event_type="compression_retry_failed",
                            attempt=attempt,
                            max_attempts=self._policy.max_attempts,
                            classification=decision.classification,
                            retry_allowed=False,
                            compression_allowed=False,
                            user_message=decision.user_message,
                            technical_message=decision.technical_message,
                            suggested_action="Compression could not fit the prompt within model limits.",
                            error_type=decision.error_type,
                        ),
                    )
                if not decision.retry_allowed:
                    await _emit_decision(
                        on_decision,
                        RetryDecisionEvent(
                            event_type="retry_skipped_non_retryable",
                            attempt=attempt,
                            max_attempts=self._policy.max_attempts,
                            classification=decision.classification,
                            retry_allowed=False,
                            compression_allowed=decision.compression_allowed,
                            user_message=decision.user_message,
                            technical_message=decision.technical_message,
                            suggested_action=decision.suggested_action,
                            error_type=decision.error_type,
                        ),
                    )
                    raise RuntimeError(_format_user_error(decision)) from exc
                if attempt >= self._policy.max_attempts:
                    await _emit_decision(
                        on_decision,
                        RetryDecisionEvent(
                            event_type="retry_exhausted",
                            attempt=attempt,
                            max_attempts=self._policy.max_attempts,
                            classification=decision.classification,
                            retry_allowed=False,
                            compression_allowed=False,
                            user_message=decision.user_message,
                            technical_message=decision.technical_message,
                            suggested_action="Automatic retries were exhausted.",
                            error_type=decision.error_type,
                        ),
                    )
                    raise RuntimeError(_format_user_error(decision)) from exc
                await _emit_decision(
                    on_decision,
                    RetryDecisionEvent(
                        event_type="retry_started",
                        attempt=attempt + 1,
                        max_attempts=self._policy.max_attempts,
                        classification=decision.classification,
                        retry_allowed=True,
                        compression_allowed=False,
                        user_message=decision.user_message,
                        technical_message=decision.technical_message,
                        suggested_action=decision.suggested_action,
                        error_type=decision.error_type,
                    ),
                )
                sleep_seconds = delay + (random.random() * self._policy.jitter_seconds if self._policy.jitter_seconds > 0 else 0.0)
                await asyncio.sleep(sleep_seconds)
                delay *= self._policy.backoff_multiplier


def _extract_status_code(text: str) -> int | None:
    match = re.search(r"\b(4\d\d|5\d\d)\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _format_user_error(decision: ProviderErrorDecision) -> str:
    return (
        f"{decision.user_message} Suggested action: {decision.suggested_action} "
        f"Technical detail: {decision.technical_message}"
    )


async def _emit_decision(
    callback: Callable[[RetryDecisionEvent], Awaitable[None] | None] | None,
    event: RetryDecisionEvent,
) -> None:
    if callback is None:
        return
    result = callback(event)
    if asyncio.iscoroutine(result):
        await result


async def _maybe_await(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value
