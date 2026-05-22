"""QA execution sandbox architecture."""

from core.qa_sandbox.artifacts import LocalSandboxArtifactStore, SandboxArtifactStore
from core.qa_sandbox.drivers import (
    BrowserSandboxDriver,
    NoopPlaywrightSandboxDriver,
    NoopSeleniumSandboxDriver,
)
from core.qa_sandbox.executor import QASandboxExecutor
from core.qa_sandbox.security import SandboxSecurityPolicy
from core.qa_sandbox.sessions import SandboxSessionManager

__all__ = [
    "BrowserSandboxDriver",
    "LocalSandboxArtifactStore",
    "NoopPlaywrightSandboxDriver",
    "NoopSeleniumSandboxDriver",
    "QASandboxExecutor",
    "SandboxArtifactStore",
    "SandboxSecurityPolicy",
    "SandboxSessionManager",
]
