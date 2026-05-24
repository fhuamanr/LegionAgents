import pytest

from core.runtime.retry import ContextWindowExceededError, RetryEngine, RetryPolicy


@pytest.mark.asyncio
async def test_retry_engine_does_not_retry_context_overflow() -> None:
    attempts = 0

    async def failing_operation() -> str:
        nonlocal attempts
        attempts += 1
        raise ContextWindowExceededError("request exceeds the available context size")

    engine = RetryEngine(RetryPolicy(max_attempts=3))
    with pytest.raises(ContextWindowExceededError):
        await engine.run(failing_operation)
    assert attempts == 1

