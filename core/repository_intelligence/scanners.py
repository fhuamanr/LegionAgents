"""Repository scanners for local, mounted, and future remote sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.contracts.repository_intelligence import (
    RepositoryFileIndex,
    RepositoryIngestionKind,
    RepositoryLanguageSummary,
    RepositoryScanRequest,
)


class RepositoryScanner(ABC):
    """Read-only repository scanner boundary."""

    @abstractmethod
    async def scan(self, request: RepositoryScanRequest) -> tuple[Path, tuple[RepositoryFileIndex, ...]]:
        """Scan a repository and return the resolved root with file indexes."""


class LocalRepositoryScanner(RepositoryScanner):
    """Scans local repositories with configurable limits and ignored directories."""

    ignored_directories: frozenset[str] = frozenset(
        {
            ".git",
            ".hg",
            ".svn",
            ".next",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            "coverage",
        }
    )
    language_by_suffix: dict[str, str] = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".java": "java",
        ".kt": "kotlin",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".md": "markdown",
        ".mmd": "mermaid",
        ".json": "json",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".sql": "sql",
        ".sh": "shell",
        ".ps1": "powershell",
        ".dockerfile": "docker",
    }
    config_names: frozenset[str] = frozenset(
        {
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "docker-compose.yml",
            "docker-compose.yaml",
            "Dockerfile",
            "next.config.ts",
            "next.config.js",
            "tailwind.config.ts",
            "tsconfig.json",
        }
    )

    async def scan(self, request: RepositoryScanRequest) -> tuple[Path, tuple[RepositoryFileIndex, ...]]:
        """Scan a local repository path."""

        if request.root_path is None:
            raise ValueError("root_path is required for local repository scanning")
        root_path = request.root_path.resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Repository path does not exist or is not a directory: {root_path}")

        files: list[RepositoryFileIndex] = []
        for path in sorted(root_path.rglob("*")):
            if not path.is_file() or self._is_ignored(path, root_path, request.include_hidden):
                continue
            size = path.stat().st_size
            if size > request.max_file_size_bytes:
                continue
            relative = path.relative_to(root_path).as_posix()
            language = self._language_for(path)
            files.append(
                RepositoryFileIndex(
                    path=relative,
                    size_bytes=size,
                    suffix=path.suffix.lower(),
                    language=language,
                    is_test=self._is_test_path(relative),
                    is_config=self._is_config(path),
                    is_documentation=self._is_documentation(path),
                )
            )
            if len(files) >= request.max_files:
                break
        return root_path, tuple(files)

    def _language_for(self, path: Path) -> str | None:
        if path.name == "Dockerfile":
            return "docker"
        return self.language_by_suffix.get(path.suffix.lower())

    def _is_ignored(self, path: Path, root_path: Path, include_hidden: bool) -> bool:
        relative_parts = path.relative_to(root_path).parts
        if any(part in self.ignored_directories for part in relative_parts):
            return True
        return not include_hidden and any(part.startswith(".") for part in relative_parts)

    def _is_config(self, path: Path) -> bool:
        return path.name in self.config_names or path.name.endswith(".config.ts") or path.name.endswith(".config.js")

    def _is_documentation(self, path: Path) -> bool:
        return path.suffix.lower() in {".md", ".rst", ".adoc"} or path.name.upper().startswith("README")

    def _is_test_path(self, relative_path: str) -> bool:
        lowered = relative_path.lower()
        return (
            lowered.startswith("tests/")
            or "/tests/" in lowered
            or lowered.endswith("_test.py")
            or lowered.endswith("test.py")
            or lowered.endswith(".spec.ts")
            or lowered.endswith(".test.ts")
            or lowered.endswith(".spec.tsx")
            or lowered.endswith(".test.tsx")
            or lowered.startswith("test_")
        )


class MountedRepositoryScanner(LocalRepositoryScanner):
    """Scans mounted repositories while preserving a separate ingestion boundary."""


class GitHubRepositoryScanner(RepositoryScanner):
    """Future GitHub ingestion boundary.

    Remote ingestion should be composed with the repository runtime/provider layer to
    clone into an isolated workspace before this scanner reads the local checkout.
    """

    async def scan(self, request: RepositoryScanRequest) -> tuple[Path, tuple[RepositoryFileIndex, ...]]:
        """Reject direct network ingestion until a provider adapter is injected."""

        raise NotImplementedError("GitHub ingestion requires a repository provider or cloned workspace adapter")


def summarize_languages(files: tuple[RepositoryFileIndex, ...]) -> tuple[RepositoryLanguageSummary, ...]:
    """Aggregate scanned files by detected language."""

    totals: dict[str, tuple[int, int]] = {}
    for file in files:
        if file.language is None:
            continue
        count, size = totals.get(file.language, (0, 0))
        totals[file.language] = (count + 1, size + file.size_bytes)
    return tuple(
        RepositoryLanguageSummary(language=language, file_count=count, total_size_bytes=size)
        for language, (count, size) in sorted(totals.items())
    )


def scanner_for(kind: RepositoryIngestionKind) -> RepositoryScanner:
    """Create a scanner for a repository ingestion kind."""

    if kind is RepositoryIngestionKind.LOCAL:
        return LocalRepositoryScanner()
    if kind is RepositoryIngestionKind.MOUNTED:
        return MountedRepositoryScanner()
    if kind is RepositoryIngestionKind.GITHUB:
        return GitHubRepositoryScanner()
    raise ValueError(f"Unsupported repository ingestion kind: {kind}")
