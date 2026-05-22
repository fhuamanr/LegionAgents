"""Execution artifact storage for QA sandboxes."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.contracts.qa_sandbox import SandboxArtifact, SandboxArtifactKind, SandboxSession
from core.qa_sandbox.security import SandboxSecurityPolicy


class SandboxArtifactStore(ABC):
    """Artifact storage boundary for screenshots, videos, logs, and evidence."""

    @abstractmethod
    async def write_bytes(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        data: bytes,
        content_type: str | None,
        description: str,
    ) -> SandboxArtifact:
        """Persist an artifact."""

    @abstractmethod
    async def write_text(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        text: str,
        content_type: str | None,
        description: str,
    ) -> SandboxArtifact:
        """Persist a text artifact."""


class LocalSandboxArtifactStore(SandboxArtifactStore):
    """Local filesystem artifact store with sandbox path isolation."""

    _directory_by_kind = {
        SandboxArtifactKind.SCREENSHOT: "screenshots",
        SandboxArtifactKind.VIDEO: "videos",
        SandboxArtifactKind.LOG: "logs",
        SandboxArtifactKind.TRACE: "traces",
        SandboxArtifactKind.TEST_EVIDENCE: "evidence",
    }
    _extension_by_kind = {
        SandboxArtifactKind.SCREENSHOT: ".png",
        SandboxArtifactKind.VIDEO: ".webm",
        SandboxArtifactKind.LOG: ".log",
        SandboxArtifactKind.TRACE: ".zip",
        SandboxArtifactKind.TEST_EVIDENCE: ".json",
    }

    async def write_bytes(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        data: bytes,
        content_type: str | None,
        description: str,
    ) -> SandboxArtifact:
        path = self._path(session, kind, name)
        path.write_bytes(data)
        return SandboxArtifact(
            kind=kind,
            path=path,
            name=name,
            description=description,
            content_type=content_type,
            metadata={"size_bytes": len(data)},
        )

    async def write_text(
        self,
        session: SandboxSession,
        kind: SandboxArtifactKind,
        name: str,
        text: str,
        content_type: str | None,
        description: str,
    ) -> SandboxArtifact:
        path = self._path(session, kind, name)
        path.write_text(text, encoding="utf-8")
        return SandboxArtifact(
            kind=kind,
            path=path,
            name=name,
            description=description,
            content_type=content_type,
            metadata={"size_bytes": len(text.encode("utf-8"))},
        )

    def _path(self, session: SandboxSession, kind: SandboxArtifactKind, name: str) -> Path:
        policy = SandboxSecurityPolicy(session.root_path)
        safe_name = policy.safe_name(name)
        directory = self._directory_by_kind[kind]
        extension = self._extension_by_kind[kind]
        path = session.artifact_path / directory / f"{safe_name}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return policy.validate_path(path)
