"""Repository analysis for the developer agent."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.agents.developer.contracts import RepositoryAnalysis, RepositoryFileSummary


class RepositoryAnalyzer(ABC):
    """Analyzes repository structure for developer prompt context."""

    @abstractmethod
    async def analyze(self, root_path: Path) -> RepositoryAnalysis:
        """Analyze repository structure."""


class FileSystemRepositoryAnalyzer(RepositoryAnalyzer):
    """Filesystem repository analyzer."""

    _ignored_directories = {
        ".git",
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

    def __init__(self, max_files: int = 1000) -> None:
        self._max_files = max_files

    async def analyze(self, root_path: Path) -> RepositoryAnalysis:
        files: list[RepositoryFileSummary] = []
        directories: set[str] = set()
        languages: set[str] = set()
        test_paths: list[str] = []

        if not root_path.exists():
            return RepositoryAnalysis(
                root_path=root_path,
                metadata={"warning": f"Repository path does not exist: {root_path}"},
            )

        for path in sorted(root_path.rglob("*")):
            if self._is_ignored(path, root_path):
                continue
            relative = path.relative_to(root_path).as_posix()
            if path.is_dir():
                directories.add(relative)
                continue
            if not path.is_file():
                continue
            files.append(
                RepositoryFileSummary(
                    path=relative,
                    suffix=path.suffix,
                    size_bytes=path.stat().st_size,
                )
            )
            language = self._language_by_suffix.get(path.suffix.lower())
            if language:
                languages.add(language)
            if self._looks_like_test_path(relative):
                test_paths.append(relative)
            if len(files) >= self._max_files:
                break

        return RepositoryAnalysis(
            root_path=root_path,
            files=tuple(files),
            directories=tuple(sorted(directories)),
            detected_languages=tuple(sorted(languages)),
            test_paths=tuple(sorted(test_paths)),
            metadata={"file_count": len(files), "directory_count": len(directories)},
        )

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
