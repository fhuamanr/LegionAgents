import pytest

from core.runtime.retry import ContextWindowExceededError, ProviderErrorClassifier, RetryEngine, RetryPolicy


@pytest.mark.asyncio
async def test_retry_engine_does_not_retry_context_overflow() -> None:
    attempts = 0

    async def failing_operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ContextWindowExceededError("request exceeds the available context size")

    engine = RetryEngine(RetryPolicy(max_attempts=3))
    with pytest.raises(RuntimeError):
        await engine.run(failing_operation)
    assert attempts == 1


def test_classifier_marks_invalid_api_key_non_retryable() -> None:
    decision = ProviderErrorClassifier().classify(ValueError("401 unauthorized invalid API key"))
    assert decision.classification == "non_retryable"
    assert decision.retry_allowed is False


def test_classifier_marks_model_not_loaded_manual_action() -> None:
    decision = ProviderErrorClassifier().classify(ValueError("model not loaded in LM Studio"))
    assert decision.classification == "retryable_after_manual_action"
    assert decision.retry_allowed is False


@pytest.mark.asyncio
async def test_retry_engine_retries_timeout_then_succeeds() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("connection timed out")
        return "ok"

    engine = RetryEngine(RetryPolicy(max_attempts=2, initial_delay_seconds=0.01, backoff_multiplier=1.0))
    result = await engine.run(operation)
    assert result == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_retry_engine_retries_on_5xx_then_exhausts() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Provider error: 503 Service Unavailable")

    engine = RetryEngine(RetryPolicy(max_attempts=2, initial_delay_seconds=0.01, backoff_multiplier=1.0))
    with pytest.raises(RuntimeError):
        await engine.run(operation)
    assert attempts == 2


@pytest.mark.asyncio
async def test_context_error_allows_single_compression_retry_only() -> None:
    attempts = 0
    compression_attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ContextWindowExceededError("request context length exceeded")

    async def compress_once(_: Exception) -> bool:
        nonlocal compression_attempts
        compression_attempts += 1
        return True

    engine = RetryEngine(RetryPolicy(max_attempts=3, initial_delay_seconds=0.01))
    with pytest.raises(RuntimeError):
        await engine.run(operation, on_compression_retry=compress_once)
    assert attempts == 2
    assert compression_attempts == 1


@pytest.mark.asyncio
async def test_retry_engine_emits_retry_skipped_event_for_non_retryable() -> None:
    events: list[str] = []

    async def operation() -> str:
        raise ValueError("invalid request payload: unsupported response_format")

    async def on_decision(event) -> None:
        events.append(event.event_type)

    engine = RetryEngine(RetryPolicy(max_attempts=3, initial_delay_seconds=0.01))
    with pytest.raises(RuntimeError):
        await engine.run(operation, on_decision=on_decision)
    assert "provider_error_classified" in events
    assert "retry_skipped_non_retryable" in events
