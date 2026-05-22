from pathlib import Path

import pytest

from core.contracts.qa_sandbox import (
    SandboxBrowserEngine,
    SandboxExecutionConfig,
    SandboxExecutionStatus,
    SandboxArtifactKind,
    SandboxStep,
    SandboxStepAction,
)
from core.qa_sandbox import QASandboxExecutor, SandboxSecurityPolicy, SandboxSessionManager
from core.qa_sandbox.drivers import BrowserSandboxDriver


@pytest.mark.asyncio
async def test_playwright_sandbox_generates_screenshots_videos_logs_and_evidence() -> None:
    executor = QASandboxExecutor(
        session_manager=SandboxSessionManager(Path.cwd() / "outputs" / "qa_sandbox_tests")
    )

    result = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.PLAYWRIGHT),
        steps=(
            SandboxStep(
                action=SandboxStepAction.NAVIGATE,
                target="http://127.0.0.1:3000/dashboard",
                description="Open dashboard.",
            ),
            SandboxStep(
                action=SandboxStepAction.SCREENSHOT,
                value="dashboard-overview",
                description="Capture dashboard screenshot.",
            ),
            SandboxStep(
                action=SandboxStepAction.RECORD_VIDEO,
                value="dashboard-flow",
                description="Record dashboard flow.",
            ),
            SandboxStep(
                action=SandboxStepAction.LOG,
                value="browser-session",
                description="Browser session completed.",
            ),
        ),
        thread_id="thread-qa-1",
    )

    artifact_kinds = {artifact.kind for artifact in result.artifacts}

    assert result.status == SandboxExecutionStatus.PASSED
    assert result.session.browser_profile_path.exists()
    assert result.metadata["docker_ready"] is True
    assert result.metadata["kubernetes_ready"] is True
    assert SandboxArtifactKind.SCREENSHOT in artifact_kinds
    assert SandboxArtifactKind.VIDEO in artifact_kinds
    assert SandboxArtifactKind.LOG in artifact_kinds
    assert SandboxArtifactKind.TEST_EVIDENCE in artifact_kinds
    assert all(artifact.path.exists() for artifact in result.artifacts)


@pytest.mark.asyncio
async def test_selenium_sandbox_uses_isolated_session_paths() -> None:
    base_path = Path.cwd() / "outputs" / "qa_sandbox_tests"
    executor = QASandboxExecutor(session_manager=SandboxSessionManager(base_path))

    first = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.SELENIUM),
        steps=(SandboxStep(action=SandboxStepAction.LOG, description="First session."),),
    )
    second = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.SELENIUM),
        steps=(SandboxStep(action=SandboxStepAction.LOG, description="Second session."),),
    )

    assert first.session.id != second.session.id
    assert first.session.browser_profile_path != second.session.browser_profile_path
    assert first.session.artifact_path != second.session.artifact_path


def test_sandbox_security_policy_rejects_path_escape() -> None:
    policy = SandboxSecurityPolicy(Path.cwd() / "outputs" / "qa_sandbox_tests")

    with pytest.raises(ValueError):
        policy.validate_path(Path.cwd().parent / "outside.png")


@pytest.mark.asyncio
async def test_sandbox_executor_retries_retryable_driver_failure() -> None:
    driver = FlakySandboxDriver()
    executor = QASandboxExecutor(
        session_manager=SandboxSessionManager(Path.cwd() / "outputs" / "qa_sandbox_tests"),
        drivers={SandboxBrowserEngine.PLAYWRIGHT: driver},
    )

    result = await executor.execute(
        config=SandboxExecutionConfig(
            engine=SandboxBrowserEngine.PLAYWRIGHT,
            resource_limits={"max_retries": 1},
        ),
        steps=(SandboxStep(action=SandboxStepAction.LOG, description="Retry step."),),
    )

    assert result.status == SandboxExecutionStatus.PASSED
    assert result.attempts == 2
    assert driver.calls == 2


class FlakySandboxDriver(BrowserSandboxDriver):
    def __init__(self) -> None:
        self.calls = 0

    async def execute_step(self, session, step):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary browser failure")
        from core.contracts.qa_sandbox import SandboxStepResult

        return SandboxStepResult(step=step, success=True, message="Recovered browser step.")
