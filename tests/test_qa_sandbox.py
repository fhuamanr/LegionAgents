from pathlib import Path
import shutil

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


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).exists()
    except Exception:
        return False


def _selenium_browser_available() -> bool:
    return any(shutil.which(name) for name in ("chromedriver", "geckodriver", "msedgedriver", "chrome", "msedge", "firefox"))


@pytest.mark.asyncio
async def test_playwright_sandbox_generates_screenshots_videos_logs_and_evidence() -> None:
    if not _playwright_available():
        pytest.skip("Playwright is not installed in this local environment.")
    executor = QASandboxExecutor(
        session_manager=SandboxSessionManager(Path.cwd() / "outputs" / "qa_sandbox_tests")
    )
    html = (Path.cwd() / "outputs" / "qa_sandbox_tests" / "fixtures" / "dashboard.html").resolve()
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<main><h1 id='dashboard'>Dashboard</h1><button id='run'>Run</button></main>", encoding="utf-8")

    result = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.PLAYWRIGHT),
        steps=(
            SandboxStep(
                action=SandboxStepAction.NAVIGATE,
                target=html.as_uri(),
                description="Open dashboard.",
            ),
            SandboxStep(
                action=SandboxStepAction.ASSERT_VISIBLE,
                target="#dashboard",
                description="Assert dashboard heading is visible.",
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
    if not _selenium_browser_available():
        pytest.skip("No local Selenium-compatible browser/driver was found.")
    base_path = Path.cwd() / "outputs" / "qa_sandbox_tests"
    executor = QASandboxExecutor(session_manager=SandboxSessionManager(base_path))
    html = (base_path / "fixtures" / "selenium.html").resolve()
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<main><h1 id='ready'>Ready</h1></main>", encoding="utf-8")

    first = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.SELENIUM),
        steps=(
            SandboxStep(action=SandboxStepAction.NAVIGATE, target=html.as_uri(), description="Open fixture."),
            SandboxStep(action=SandboxStepAction.ASSERT_VISIBLE, target="#ready", description="Assert fixture."),
        ),
    )
    second = await executor.execute(
        config=SandboxExecutionConfig(engine=SandboxBrowserEngine.SELENIUM),
        steps=(
            SandboxStep(action=SandboxStepAction.NAVIGATE, target=html.as_uri(), description="Open fixture."),
            SandboxStep(action=SandboxStepAction.SCREENSHOT, value="selenium-second", description="Capture screenshot."),
        ),
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
