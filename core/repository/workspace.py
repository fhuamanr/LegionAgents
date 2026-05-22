"""Isolated repository workspace management."""

from pathlib import Path
from uuid import uuid4

from core.contracts.repository import RepositoryWorkspace


class IsolatedWorkspaceManager:
    """Creates isolated workspaces for agent repository operations."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base_path = (base_path or Path.cwd() / "outputs" / "repositories").resolve()

    @property
    def base_path(self) -> Path:
        """Workspace base path."""

        return self._base_path

    async def create_workspace(
        self,
        agent_name: str,
        thread_id: str | None = None,
        repository_name: str = "repository",
    ) -> RepositoryWorkspace:
        """Create an isolated workspace descriptor and directories."""

        workspace_id = uuid4()
        root_path = (self._base_path / agent_name / str(workspace_id)).resolve()
        repository_path = (root_path / self._safe_name(repository_name)).resolve()
        if not self._is_within_base(root_path) or not self._is_within_base(repository_path):
            raise ValueError("Workspace path escapes repository workspace base.")
        repository_path.parent.mkdir(parents=True, exist_ok=True)
        return RepositoryWorkspace(
            id=workspace_id,
            root_path=root_path,
            repository_path=repository_path,
            agent_name=agent_name,
            thread_id=thread_id,
            metadata={"base_path": str(self._base_path)},
        )

    def _safe_name(self, value: str) -> str:
        safe = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in value)
        return safe.strip(".-") or "repository"

    def _is_within_base(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._base_path)
        except ValueError:
            return False
        return True
