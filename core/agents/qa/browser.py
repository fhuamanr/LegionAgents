"""Browser abstraction layer for real QA automation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from core.agents.qa.contracts import BrowserAction, BrowserAutomationResult, BrowserAutomationStep
from core.contracts.qa_sandbox import (
    SandboxBrowserEngine,
    SandboxExecutionConfig,
    SandboxExecutionStatus,
    SandboxStep,
    SandboxStepAction,
)
from core.qa_sandbox import QASandboxExecutor, SandboxSessionManager


class BrowserAutomationDriver(ABC):
    """Browser automation boundary for Playwright/Selenium adapters."""

    @abstractmethod
    async def execute(self, step: BrowserAutomationStep) -> BrowserAutomationResult:
        """Execute one browser automation step."""


class SandboxBrowserAutomationDriver(BrowserAutomationDriver):
    """Runs QA browser automation through the real sandbox executor."""

    def __init__(
        self,
        output_root: Path | None = None,
        engine: SandboxBrowserEngine = SandboxBrowserEngine.PLAYWRIGHT,
    ) -> None:
        self._executor = QASandboxExecutor(
            session_manager=SandboxSessionManager(output_root or Path.cwd() / "outputs" / "qa_agent_browser")
        )
        self._engine = engine

    async def execute(self, step: BrowserAutomationStep) -> BrowserAutomationResult:
        sandbox_step = SandboxStep(
            action=self._action(step.action),
            target=step.target,
            value=step.value,
            description=step.description,
        )
        result = await self._executor.execute(
            config=SandboxExecutionConfig(engine=self._engine),
            steps=(sandbox_step,),
        )
        screenshot_path = None
        for artifact in result.artifacts:
            if artifact.kind.value == "screenshot":
                screenshot_path = artifact.path.as_posix()
                break
        return BrowserAutomationResult(
            step=step,
            success=result.status == SandboxExecutionStatus.PASSED,
            screenshot_path=screenshot_path,
            message="\n".join(result.logs + result.errors),
        )

    def _action(self, action: BrowserAction) -> SandboxStepAction:
        return {
            BrowserAction.NAVIGATE: SandboxStepAction.NAVIGATE,
            BrowserAction.CLICK: SandboxStepAction.CLICK,
            BrowserAction.FILL: SandboxStepAction.FILL,
            BrowserAction.SCREENSHOT: SandboxStepAction.SCREENSHOT,
            BrowserAction.ASSERT_VISIBLE: SandboxStepAction.ASSERT_VISIBLE,
        }[action]


class BrowserAutomationService:
    """Runs browser automation steps through an injected real driver."""

    def __init__(self, driver: BrowserAutomationDriver | None = None) -> None:
        self._driver = driver or SandboxBrowserAutomationDriver()

    async def run(
        self,
        steps: tuple[BrowserAutomationStep, ...],
    ) -> tuple[BrowserAutomationResult, ...]:
        results: list[BrowserAutomationResult] = []
        for step in steps:
            results.append(await self._driver.execute(step))
        return tuple(results)


class ScreenshotPathFactory:
    """Creates deterministic screenshot evidence paths."""

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root

    def create(self, name: str) -> str:
        safe_name = name.lower().replace(" ", "-").replace("_", "-")
        return str((self._output_root / "screenshots" / f"{safe_name}.png").as_posix())
