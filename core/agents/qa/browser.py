"""Browser abstraction layer for QA automation."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.agents.qa.contracts import BrowserAction, BrowserAutomationResult, BrowserAutomationStep


class BrowserAutomationDriver(ABC):
    """Browser automation boundary for Playwright/Selenium adapters."""

    @abstractmethod
    async def execute(self, step: BrowserAutomationStep) -> BrowserAutomationResult:
        """Execute one browser automation step."""


class NoopBrowserAutomationDriver(BrowserAutomationDriver):
    """Local no-op driver used until Playwright/Selenium adapters are wired."""

    async def execute(self, step: BrowserAutomationStep) -> BrowserAutomationResult:
        screenshot_path = step.value if step.action == BrowserAction.SCREENSHOT else None
        return BrowserAutomationResult(
            step=step,
            success=True,
            screenshot_path=screenshot_path,
            message="No-op browser driver executed step.",
        )


class BrowserAutomationService:
    """Runs browser automation steps through an injected driver."""

    def __init__(self, driver: BrowserAutomationDriver | None = None) -> None:
        self._driver = driver or NoopBrowserAutomationDriver()

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

