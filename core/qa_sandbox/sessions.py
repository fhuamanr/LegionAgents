"""Browser sandbox session management."""

from pathlib import Path
from uuid import UUID, uuid4

from core.contracts.qa_sandbox import SandboxExecutionConfig, SandboxSession
from core.qa_sandbox.security import SandboxSecurityPolicy


class SandboxSessionManager:
    """Creates isolated browser sessions for QA execution."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base_path = (base_path or Path.cwd() / "outputs" / "qa_sandbox").resolve()
        self._policy = SandboxSecurityPolicy(self._base_path)

    async def create_session(
        self,
        config: SandboxExecutionConfig,
        agent_name: str = "qa",
        execution_id: UUID | None = None,
        thread_id: str | None = None,
    ) -> SandboxSession:
        """Create isolated directories for one browser execution session."""

        session_id = uuid4()
        root_path = self._policy.validate_path(self._base_path / agent_name / str(session_id))
        artifact_path = self._policy.validate_path(root_path / "artifacts")
        browser_profile_path = self._policy.validate_path(root_path / "browser-profile")
        for path in (
            artifact_path / "screenshots",
            artifact_path / "videos",
            artifact_path / "logs",
            artifact_path / "traces",
            artifact_path / "evidence",
            browser_profile_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

        return SandboxSession(
            id=session_id,
            agent_name=agent_name,
            execution_id=execution_id or uuid4(),
            thread_id=thread_id,
            root_path=root_path,
            artifact_path=artifact_path,
            browser_profile_path=browser_profile_path,
            config=config,
            metadata={
                "docker_ready": True,
                "kubernetes_ready": True,
                "session_isolation": "dedicated_artifact_and_browser_profile_paths",
            },
        )
