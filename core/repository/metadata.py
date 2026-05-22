"""Repository metadata extraction and summarization."""

from pathlib import Path

from core.contracts.repository import (
    RepositoryMetadata,
    RepositoryProvider,
    RepositorySummary,
    RepositoryWorkspace,
)
from core.repository.git import GitService


class RepositorySummarizer:
    """Extracts metadata and compact summaries from repository workspaces."""

    _ignored_directories = {
        ".git",
        ".next",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
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
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
    }

    def __init__(self, git: GitService | None = None, max_files: int = 500) -> None:
        self._git = git or GitService()
        self._max_files = max_files

    async def metadata(self, workspace: RepositoryWorkspace) -> RepositoryMetadata:
        """Extract repository metadata."""

        remote_url = await self._git.remote_url(workspace)
        branch = await self._git.current_branch(workspace)
        head_sha = await self._git.head_sha(workspace)
        status = await self._git.status(workspace)
        files, languages, test_paths = self._scan(workspace.repository_path)
        return RepositoryMetadata(
            provider=self._provider(remote_url),
            remote_url=remote_url,
            current_branch=branch,
            head_sha=head_sha,
            is_dirty=bool(status.stdout.strip()),
            detected_languages=tuple(sorted(languages)),
            file_count=len(files),
            test_paths=tuple(sorted(test_paths)),
            metadata={"status_return_code": status.return_code},
        )

    async def summarize(self, workspace: RepositoryWorkspace) -> RepositorySummary:
        """Build a repository summary suitable for agent context."""

        metadata = await self.metadata(workspace)
        top_level_directories = self._top_level_directories(workspace.repository_path)
        notable_files = self._notable_files(workspace.repository_path)
        language_text = ", ".join(metadata.detected_languages) or "unknown languages"
        summary = (
            f"Repository on branch {metadata.current_branch or 'unknown'} contains "
            f"{metadata.file_count} scanned files across {language_text}."
        )
        return RepositorySummary(
            metadata=metadata,
            top_level_directories=top_level_directories,
            notable_files=notable_files,
            summary=summary,
        )

    def _scan(self, root_path: Path) -> tuple[list[str], set[str], list[str]]:
        files: list[str] = []
        languages: set[str] = set()
        test_paths: list[str] = []
        if not root_path.exists():
            return files, languages, test_paths
        for path in sorted(root_path.rglob("*")):
            if self._is_ignored(path, root_path) or not path.is_file():
                continue
            relative = path.relative_to(root_path).as_posix()
            files.append(relative)
            language = self._language_by_suffix.get(path.suffix.lower())
            if language:
                languages.add(language)
            if self._looks_like_test_path(relative):
                test_paths.append(relative)
            if len(files) >= self._max_files:
                break
        return files, languages, test_paths

    def _top_level_directories(self, root_path: Path) -> tuple[str, ...]:
        if not root_path.exists():
            return tuple()
        return tuple(sorted(path.name for path in root_path.iterdir() if path.is_dir() and path.name != ".git"))

    def _notable_files(self, root_path: Path) -> tuple[str, ...]:
        names = {
            "README.md",
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "next.config.ts",
            "Dockerfile",
        }
        return tuple(sorted(path.name for path in root_path.iterdir() if path.is_file() and path.name in names))

    def _provider(self, remote_url: str | None) -> RepositoryProvider:
        lowered = (remote_url or "").lower()
        if "github.com" in lowered:
            return RepositoryProvider.GITHUB
        if "gitlab.com" in lowered:
            return RepositoryProvider.GITLAB
        if remote_url:
            return RepositoryProvider.LOCAL
        return RepositoryProvider.UNKNOWN

    def _is_ignored(self, path: Path, root_path: Path) -> bool:
        relative_parts = path.relative_to(root_path).parts
        return any(part in self._ignored_directories for part in relative_parts)

    def _looks_like_test_path(self, relative_path: str) -> bool:
        lowered = relative_path.lower()
        return (
            lowered.startswith("tests/")
            or "/tests/" in lowered
            or lowered.endswith("_test.py")
            or lowered.endswith("test.py")
            or lowered.startswith("test_")
        )
