"""Repository-aware PR review context."""

from pathlib import Path

from core.contracts.pr_review import PRReviewRequest
from core.contracts.repository import DiffAnalysis, PullRequestPreparation


class PRReviewContext:
    """Convenience wrapper around PR review inputs."""

    def __init__(self, request: PRReviewRequest) -> None:
        self.request = request
        self.pull_request = request.pull_request
        self.diff = self._diff(request.pull_request, request.diff)
        self.repository_root = request.repository_root
        self.changed_paths = tuple(change.path for change in self.diff.files)

    def read_changed_file(self, path: str) -> str:
        """Read a changed repository file when a repository root is available."""

        if self.repository_root is None:
            return ""
        candidate = (self.repository_root / path).resolve()
        root = self.repository_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return ""
        if not candidate.exists() or not candidate.is_file():
            return ""
        try:
            return candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def has_changed_path(self, *parts: str) -> bool:
        lowered = tuple(path.lower() for path in self.changed_paths)
        return any(any(part.lower() in path for part in parts) for path in lowered)

    def changed_source_files(self) -> tuple[str, ...]:
        return tuple(
            path
            for path in self.changed_paths
            if Path(path).suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs"}
        )

    def changed_test_files(self) -> tuple[str, ...]:
        return tuple(path for path in self.changed_paths if self._is_test_path(path))

    def changed_documentation_files(self) -> tuple[str, ...]:
        return tuple(path for path in self.changed_paths if Path(path).suffix.lower() in {".md", ".rst", ".adoc"})

    def _diff(self, pull_request: PullRequestPreparation | None, diff: DiffAnalysis | None) -> DiffAnalysis:
        if diff is not None:
            return diff
        if pull_request is not None:
            return pull_request.diff
        return DiffAnalysis(summary="No diff provided.")

    def _is_test_path(self, path: str) -> bool:
        lowered = path.lower()
        return (
            lowered.startswith("tests/")
            or "/tests/" in lowered
            or lowered.endswith("_test.py")
            or lowered.endswith(".test.ts")
            or lowered.endswith(".test.tsx")
            or lowered.endswith(".spec.ts")
            or lowered.endswith(".spec.tsx")
        )
