"""Repository diff analysis."""

from pathlib import Path

from core.contracts.repository import (
    DiffAnalysis,
    DiffFileChange,
    RepositoryChangeKind,
    RepositoryWorkspace,
)
from core.repository.git import GitService


class DiffAnalyzer:
    """Analyzes git diffs into structured change summaries."""

    _kind_by_status = {
        "A": RepositoryChangeKind.ADDED,
        "M": RepositoryChangeKind.MODIFIED,
        "D": RepositoryChangeKind.DELETED,
        "R": RepositoryChangeKind.RENAMED,
        "C": RepositoryChangeKind.COPIED,
        "U": RepositoryChangeKind.UNMERGED,
    }
    _language_by_suffix = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".md": "markdown",
        ".mmd": "mermaid",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
    }

    def __init__(self, git: GitService | None = None) -> None:
        self._git = git or GitService()

    async def analyze(
        self,
        workspace: RepositoryWorkspace,
        base_ref: str | None = None,
        target_ref: str | None = None,
    ) -> DiffAnalysis:
        """Analyze changed files between refs or the working tree."""

        ref_args = self._ref_args(base_ref, target_ref)
        name_status = await self._git.diff(workspace, "--name-status", *ref_args)
        numstat = await self._git.diff(workspace, "--numstat", *ref_args)
        changes = self._merge_changes(name_status.stdout, numstat.stdout)
        return DiffAnalysis(
            base_ref=base_ref,
            target_ref=target_ref,
            files=changes,
            summary=self._summary(changes),
            risk_flags=self._risk_flags(changes),
            metadata={
                "file_count": len(changes),
                "total_additions": sum(change.additions for change in changes),
                "total_deletions": sum(change.deletions for change in changes),
            },
        )

    def _ref_args(self, base_ref: str | None, target_ref: str | None) -> tuple[str, ...]:
        if base_ref and target_ref:
            return (f"{base_ref}...{target_ref}",)
        if base_ref:
            return (base_ref,)
        return tuple()

    def _merge_changes(self, name_status: str, numstat: str) -> tuple[DiffFileChange, ...]:
        by_path: dict[str, DiffFileChange] = {}
        for line in name_status.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0]
            kind = self._kind_by_status.get(status[0], RepositoryChangeKind.UNKNOWN)
            previous_path: str | None = None
            path = parts[-1]
            if kind in {RepositoryChangeKind.RENAMED, RepositoryChangeKind.COPIED} and len(parts) >= 3:
                previous_path = parts[1]
            by_path[path] = DiffFileChange(
                path=path,
                kind=kind,
                previous_path=previous_path,
                language=self._language(path),
            )

        for line in numstat.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            additions = self._safe_int(parts[0])
            deletions = self._safe_int(parts[1])
            path = parts[-1]
            current = by_path.get(path)
            by_path[path] = (current or DiffFileChange(path=path, language=self._language(path))).model_copy(
                update={"additions": additions, "deletions": deletions}
            )
        return tuple(by_path[path] for path in sorted(by_path))

    def _summary(self, changes: tuple[DiffFileChange, ...]) -> str:
        additions = sum(change.additions for change in changes)
        deletions = sum(change.deletions for change in changes)
        return f"{len(changes)} files changed, {additions} additions, {deletions} deletions."

    def _risk_flags(self, changes: tuple[DiffFileChange, ...]) -> tuple[str, ...]:
        flags: list[str] = []
        paths = [change.path.lower() for change in changes]
        if any("security" in path or ".env" in path for path in paths):
            flags.append("security_sensitive_files_changed")
        if any(path.startswith("tests/") or "/tests/" in path for path in paths):
            flags.append("tests_changed")
        if sum(change.additions + change.deletions for change in changes) > 500:
            flags.append("large_diff")
        return tuple(flags)

    def _language(self, path: str) -> str | None:
        return self._language_by_suffix.get(Path(path).suffix.lower())

    def _safe_int(self, value: str) -> int:
        return int(value) if value.isdigit() else 0
