"""Real browser sandbox drivers for Playwright and Selenium."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from core.contracts.qa_sandbox import (
    SandboxArtifact,
    SandboxArtifactKind,
    SandboxSession,
    SandboxStep,
    SandboxStepAction,
    SandboxStepResult,
)
from core.qa_sandbox.artifacts import LocalSandboxArtifactStore, SandboxArtifactStore
from core.qa_sandbox.security import SandboxSecurityPolicy


class BrowserSandboxDriver:
    """Browser execution driver boundary for Playwright and Selenium adapters."""

    async def execute_step(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        """Execute a single sandbox step."""

        raise NotImplementedError

    async def finalize(
        self,
        session: SandboxSession,
        step_results: tuple[SandboxStepResult, ...],
    ) -> tuple[SandboxArtifact, ...]:
        """Finalize a browser session and emit evidence artifacts."""

        return tuple()


class PlaywrightSandboxDriver(BrowserSandboxDriver):
    """Actual Playwright browser driver with screenshots, assertions, and videos."""

    def __init__(self, artifact_store: SandboxArtifactStore | None = None) -> None:
        self._artifact_store = artifact_store or LocalSandboxArtifactStore()
        self._sessions: dict[UUID, dict[str, Any]] = {}

    async def execute_step(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        page = await self._page(session)
        artifacts: list[SandboxArtifact] = []

        if step.action == SandboxStepAction.NAVIGATE:
            if not step.target:
                raise ValueError("NAVIGATE requires target URL.")
            await page.goto(step.target, wait_until=step.metadata.get("wait_until", "domcontentloaded"))
        elif step.action == SandboxStepAction.CLICK:
            await page.locator(self._selector(step)).click()
        elif step.action == SandboxStepAction.FILL:
            await page.locator(self._selector(step)).fill(step.value or "")
        elif step.action == SandboxStepAction.ASSERT_VISIBLE:
            await page.locator(self._selector(step)).wait_for(state="visible")
        elif step.action == SandboxStepAction.SCREENSHOT:
            data = await page.screenshot(full_page=bool(step.metadata.get("full_page", True)))
            artifacts.append(
                await self._artifact_store.write_bytes(
                    session=session,
                    kind=SandboxArtifactKind.SCREENSHOT,
                    name=step.value or "screenshot",
                    data=data,
                    content_type="image/png",
                    description=step.description,
                )
            )
        elif step.action == SandboxStepAction.RECORD_VIDEO:
            await self._artifact_store.write_text(
                session=session,
                kind=SandboxArtifactKind.LOG,
                name=step.value or "video-recording-requested",
                text="Playwright video recording is active for this browser context.",
                content_type="text/plain",
                description=step.description,
            )
        elif step.action == SandboxStepAction.LOG:
            artifacts.append(
                await self._artifact_store.write_text(
                    session=session,
                    kind=SandboxArtifactKind.LOG,
                    name=step.value or "browser-step",
                    text=step.description,
                    content_type="text/plain",
                    description="Sandbox execution log.",
                )
            )
        else:
            raise ValueError(f"Unsupported Playwright sandbox action: {step.action}")

        return SandboxStepResult(
            step=step,
            success=True,
            message=f"Playwright executed {step.action.value}.",
            artifacts=tuple(artifacts),
            metadata={"engine": "playwright", "browser_name": session.config.browser_name},
        )

    async def finalize(
        self,
        session: SandboxSession,
        step_results: tuple[SandboxStepResult, ...],
    ) -> tuple[SandboxArtifact, ...]:
        state = self._sessions.pop(session.id, None)
        video_artifacts: list[SandboxArtifact] = []
        if state is not None:
            page = state["page"]
            context = state["context"]
            browser = state["browser"]
            video = page.video
            await context.close()
            await browser.close()
            if video is not None:
                try:
                    source = Path(await video.path())
                    if source.exists():
                        video_artifacts.append(self._register_artifact(session, SandboxArtifactKind.VIDEO, source, "Playwright Video", "Recorded Playwright browser session.", "video/webm"))
                except Exception:
                    pass
            await state["playwright"].stop()
        evidence = await self._write_evidence(session, step_results)
        return tuple(video_artifacts) + evidence

    async def _page(self, session: SandboxSession):
        state = self._sessions.get(session.id)
        if state is not None:
            return state["page"]
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Install `playwright` and run `playwright install`.") from exc

        playwright = await async_playwright().start()
        browser_type = getattr(playwright, session.config.browser_name, playwright.chromium)
        browser = await browser_type.launch(headless=session.config.headless)
        context = await browser.new_context(
            record_video_dir=str(session.artifact_path / "videos"),
            user_agent=session.config.metadata.get("user_agent"),
        )
        page = await context.new_page()
        self._sessions[session.id] = {"playwright": playwright, "browser": browser, "context": context, "page": page}
        return page

    def _selector(self, step: SandboxStep) -> str:
        selector = step.target or step.value
        if not selector:
            raise ValueError(f"{step.action.value} requires target selector.")
        return selector

    async def _write_evidence(
        self,
        session: SandboxSession,
        step_results: tuple[SandboxStepResult, ...],
    ) -> tuple[SandboxArtifact, ...]:
        evidence = _evidence_payload(session, step_results)
        return (
            await self._artifact_store.write_text(
                session=session,
                kind=SandboxArtifactKind.TEST_EVIDENCE,
                name="test-evidence",
                text=json.dumps(evidence, indent=2),
                content_type="application/json",
                description="Structured QA sandbox test evidence.",
            ),
            await self._artifact_store.write_text(
                session=session,
                kind=SandboxArtifactKind.LOG,
                name="execution",
                text="\n".join(result.message for result in step_results),
                content_type="text/plain",
                description="Sandbox execution log.",
            ),
        )

    def _register_artifact(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        path: Path,
        name: str,
        description: str,
        content_type: str,
    ) -> SandboxArtifact:
        validated = SandboxSecurityPolicy(session.root_path).validate_path(path)
        return SandboxArtifact(
            kind=kind,
            path=validated,
            name=name,
            description=description,
            content_type=content_type,
            metadata={"size_bytes": validated.stat().st_size if validated.exists() else 0},
        )


class SeleniumSandboxDriver(BrowserSandboxDriver):
    """Actual Selenium browser driver with screenshots and DOM assertions."""

    def __init__(self, artifact_store: SandboxArtifactStore | None = None) -> None:
        self._artifact_store = artifact_store or LocalSandboxArtifactStore()
        self._drivers: dict[UUID, Any] = {}

    async def execute_step(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        import asyncio

        return await asyncio.to_thread(self._execute_step_sync, session, step)

    async def finalize(
        self,
        session: SandboxSession,
        step_results: tuple[SandboxStepResult, ...],
    ) -> tuple[SandboxArtifact, ...]:
        import asyncio

        driver = self._drivers.pop(session.id, None)
        if driver is not None:
            await asyncio.to_thread(driver.quit)
        return await self._write_evidence(session, step_results)

    def _execute_step_sync(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        driver = self._driver(session)
        artifacts: list[SandboxArtifact] = []
        if step.action == SandboxStepAction.NAVIGATE:
            if not step.target:
                raise ValueError("NAVIGATE requires target URL.")
            driver.get(step.target)
        elif step.action == SandboxStepAction.CLICK:
            self._element(driver, step).click()
        elif step.action == SandboxStepAction.FILL:
            element = self._element(driver, step)
            element.clear()
            element.send_keys(step.value or "")
        elif step.action == SandboxStepAction.ASSERT_VISIBLE:
            element = self._element(driver, step)
            if not element.is_displayed():
                raise AssertionError(f"Element is not visible: {step.target}")
        elif step.action == SandboxStepAction.SCREENSHOT:
            data = driver.get_screenshot_as_png()
            artifacts.append(self._write_bytes_sync(session, SandboxArtifactKind.SCREENSHOT, step.value or "screenshot", data, "image/png", step.description))
        elif step.action == SandboxStepAction.LOG:
            artifacts.append(self._write_text_sync(session, SandboxArtifactKind.LOG, step.value or "browser-step", step.description, "text/plain", "Sandbox execution log."))
        elif step.action == SandboxStepAction.RECORD_VIDEO:
            raise RuntimeError("Selenium does not provide native video recording in this local driver; use Playwright for recorded browser video.")
        else:
            raise ValueError(f"Unsupported Selenium sandbox action: {step.action}")
        return SandboxStepResult(
            step=step,
            success=True,
            message=f"Selenium executed {step.action.value}.",
            artifacts=tuple(artifacts),
            metadata={"engine": "selenium", "browser_name": session.config.browser_name},
        )

    def _driver(self, session: SandboxSession):
        existing = self._drivers.get(session.id)
        if existing is not None:
            return existing
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
        except ImportError as exc:
            raise RuntimeError("Selenium is not installed.") from exc

        browser_name = session.config.browser_name.lower()
        if browser_name in {"edge", "msedge"}:
            options = EdgeOptions()
            if session.config.headless:
                options.add_argument("--headless=new")
            options.add_argument(f"--user-data-dir={session.browser_profile_path}")
            driver = webdriver.Edge(options=options)
        elif browser_name == "firefox":
            options = FirefoxOptions()
            options.profile = str(session.browser_profile_path)
            options.headless = session.config.headless
            driver = webdriver.Firefox(options=options)
        else:
            options = ChromeOptions()
            if session.config.headless:
                options.add_argument("--headless=new")
            options.add_argument(f"--user-data-dir={session.browser_profile_path}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=options)
        self._drivers[session.id] = driver
        return driver

    def _element(self, driver: Any, step: SandboxStep):
        from selenium.webdriver.common.by import By

        selector = step.target or step.value
        if not selector:
            raise ValueError(f"{step.action.value} requires target selector.")
        return driver.find_element(By.CSS_SELECTOR, selector)

    def _write_bytes_sync(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        data: bytes,
        content_type: str,
        description: str,
    ) -> SandboxArtifact:
        path = self._artifact_path(session, kind, name)
        path.write_bytes(data)
        return SandboxArtifact(kind=kind, path=path, name=name, description=description, content_type=content_type, metadata={"size_bytes": len(data)})

    def _write_text_sync(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        text: str,
        content_type: str,
        description: str,
    ) -> SandboxArtifact:
        path = self._artifact_path(session, kind, name)
        path.write_text(text, encoding="utf-8")
        return SandboxArtifact(kind=kind, path=path, name=name, description=description, content_type=content_type, metadata={"size_bytes": len(text.encode("utf-8"))})

    def _artifact_path(self, session: SandboxSession, kind: SandboxArtifactKind, name: str) -> Path:
        store = LocalSandboxArtifactStore()
        return store._path(session, kind, name)  # noqa: SLF001 - local adapter reuses sandbox path policy.

    async def _write_evidence(
        self,
        session: SandboxSession,
        step_results: tuple[SandboxStepResult, ...],
    ) -> tuple[SandboxArtifact, ...]:
        evidence = _evidence_payload(session, step_results)
        return (
            await self._artifact_store.write_text(
                session=session,
                kind=SandboxArtifactKind.TEST_EVIDENCE,
                name="test-evidence",
                text=json.dumps(evidence, indent=2),
                content_type="application/json",
                description="Structured QA sandbox test evidence.",
            ),
            await self._artifact_store.write_text(
                session=session,
                kind=SandboxArtifactKind.LOG,
                name="execution",
                text="\n".join(result.message for result in step_results),
                content_type="text/plain",
                description="Sandbox execution log.",
            ),
        )


def _evidence_payload(session: SandboxSession, step_results: tuple[SandboxStepResult, ...]) -> dict[str, Any]:
    return {
        "session_id": str(session.id),
        "engine": session.config.engine.value,
        "isolation_mode": session.config.isolation_mode.value,
        "steps": [
            {
                "action": result.step.action.value,
                "description": result.step.description,
                "success": result.success,
                "artifacts": [str(artifact.path) for artifact in result.artifacts],
            }
            for result in step_results
        ],
    }
