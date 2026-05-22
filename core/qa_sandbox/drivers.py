"""Browser sandbox driver boundaries."""

import json
from abc import ABC, abstractmethod

from core.contracts.qa_sandbox import (
    SandboxArtifact,
    SandboxArtifactKind,
    SandboxSession,
    SandboxStep,
    SandboxStepAction,
    SandboxStepResult,
)
from core.qa_sandbox.artifacts import LocalSandboxArtifactStore, SandboxArtifactStore


class BrowserSandboxDriver(ABC):
    """Browser execution driver boundary for Playwright and Selenium adapters."""

    @abstractmethod
    async def execute_step(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        """Execute a single sandbox step."""


class _NoopBrowserSandboxDriver(BrowserSandboxDriver):
    """Deterministic local driver used until real browser adapters are wired."""

    def __init__(self, artifact_store: SandboxArtifactStore | None = None) -> None:
        self._artifact_store = artifact_store or LocalSandboxArtifactStore()

    async def execute_step(self, session: SandboxSession, step: SandboxStep) -> SandboxStepResult:
        artifacts: list[SandboxArtifact] = []
        if step.action == SandboxStepAction.SCREENSHOT:
            artifacts.append(await self._write_screenshot(session, step))
        elif step.action == SandboxStepAction.RECORD_VIDEO:
            artifacts.append(await self._write_video(session, step))
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

        return SandboxStepResult(
            step=step,
            success=True,
            message=f"{self.__class__.__name__} executed {step.action.value}.",
            artifacts=tuple(artifacts),
            metadata={
                "engine": session.config.engine.value,
                "headless": session.config.headless,
                "browser_name": session.config.browser_name,
                "driver": self.__class__.__name__,
            },
        )

    async def finalize(self, session: SandboxSession, step_results: tuple[SandboxStepResult, ...]) -> tuple[SandboxArtifact, ...]:
        """Write final evidence/log artifacts for the session."""

        evidence = {
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

    async def _write_screenshot(self, session: SandboxSession, step: SandboxStep) -> SandboxArtifact:
        return await self._artifact_store.write_bytes(
            session=session,
            kind=SandboxArtifactKind.SCREENSHOT,
            name=step.value or "screenshot",
            data=_minimal_png(),
            content_type="image/png",
            description=step.description,
        )

    async def _write_video(self, session: SandboxSession, step: SandboxStep) -> SandboxArtifact:
        return await self._artifact_store.write_bytes(
            session=session,
            kind=SandboxArtifactKind.VIDEO,
            name=step.value or "recording",
            data=b"WEBM placeholder recording for sandbox architecture.\n",
            content_type="video/webm",
            description=step.description,
        )


class NoopPlaywrightSandboxDriver(_NoopBrowserSandboxDriver):
    """Playwright adapter placeholder with isolated artifact behavior."""


class NoopSeleniumSandboxDriver(_NoopBrowserSandboxDriver):
    """Selenium adapter placeholder with isolated artifact behavior."""


def _minimal_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
