"""Retry-safe QA sandbox executor."""

import logging

from core.contracts.qa_sandbox import (
    SandboxArtifact,
    SandboxBrowserEngine,
    SandboxExecutionConfig,
    SandboxExecutionResult,
    SandboxExecutionStatus,
    SandboxSession,
    SandboxStep,
    SandboxStepResult,
)
from core.qa_sandbox.drivers import (
    BrowserSandboxDriver,
    PlaywrightSandboxDriver,
    SeleniumSandboxDriver,
)
from core.qa_sandbox.sessions import SandboxSessionManager


class QASandboxExecutor:
    """Executes isolated browser test sessions with retry-safe semantics."""

    def __init__(
        self,
        session_manager: SandboxSessionManager | None = None,
        drivers: dict[SandboxBrowserEngine, BrowserSandboxDriver] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._session_manager = session_manager or SandboxSessionManager()
        self._drivers = drivers or {
            SandboxBrowserEngine.PLAYWRIGHT: PlaywrightSandboxDriver(),
            SandboxBrowserEngine.SELENIUM: SeleniumSandboxDriver(),
        }
        self._logger = logger or logging.getLogger(__name__)

    async def execute(
        self,
        config: SandboxExecutionConfig,
        steps: tuple[SandboxStep, ...],
        agent_name: str = "qa",
        thread_id: str | None = None,
    ) -> SandboxExecutionResult:
        """Execute a complete sandbox session."""

        session = await self._session_manager.create_session(
            config=config,
            agent_name=agent_name,
            thread_id=thread_id,
        )
        max_attempts = config.resource_limits.max_retries + 1
        errors: list[str] = []
        logs: list[str] = []

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._execute_attempt(session, steps, attempt, logs)
            except Exception as exc:
                errors.append(str(exc))
                logs.append(f"attempt={attempt} failed: {exc}")
                self._logger.warning(
                    "qa_sandbox_attempt_failed",
                    extra={"session_id": str(session.id), "attempt": attempt, "error": str(exc)},
                )
                if attempt >= max_attempts:
                    return SandboxExecutionResult(
                        session=session,
                        status=SandboxExecutionStatus.FAILED,
                        attempts=attempt,
                        logs=tuple(logs),
                        errors=tuple(errors),
                    )

        return SandboxExecutionResult(
            session=session,
            status=SandboxExecutionStatus.FAILED,
            attempts=max_attempts,
            logs=tuple(logs),
            errors=tuple(errors or ("Sandbox execution ended unexpectedly.",)),
        )

    async def _execute_attempt(
        self,
        session: SandboxSession,
        steps: tuple[SandboxStep, ...],
        attempt: int,
        logs: list[str],
    ) -> SandboxExecutionResult:
        driver = self._driver_for(session.config.engine)
        logs.append(f"attempt={attempt} status=running engine={session.config.engine.value}")
        step_results: list[SandboxStepResult] = []
        artifacts: list[SandboxArtifact] = []

        for step in steps:
            result = await driver.execute_step(session, step)
            step_results.append(result)
            artifacts.extend(result.artifacts)
            logs.append(result.message)
            if not result.success:
                raise RuntimeError(result.message or f"Sandbox step failed: {step.action.value}")

        final_artifacts = await driver.finalize(session, tuple(step_results))
        artifacts.extend(final_artifacts)

        status = SandboxExecutionStatus.PASSED if all(result.success for result in step_results) else SandboxExecutionStatus.FAILED
        return SandboxExecutionResult(
            session=session,
            status=status,
            attempts=attempt,
            step_results=tuple(step_results),
            artifacts=tuple(artifacts),
            logs=tuple(logs),
            metadata={
                "docker_ready": True,
                "kubernetes_ready": True,
                "browser_session_isolated": True,
                "artifact_count": len(artifacts),
            },
        )

    def _driver_for(self, engine: SandboxBrowserEngine) -> BrowserSandboxDriver:
        try:
            return self._drivers[engine]
        except KeyError as exc:
            raise ValueError(f"No QA sandbox driver registered for engine: {engine}") from exc
