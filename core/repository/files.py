"""Safe repository file modification engine."""

from __future__ import annotations

from pathlib import Path

from core.contracts.repository import (
    RepositoryFileModification,
    RepositoryFileOperation,
    RepositoryModificationRequest,
    RepositoryModificationResult,
    RepositoryWorkspace,
)


class RepositoryFileModificationEngine:
    """Applies concrete file changes inside an isolated repository workspace."""

    _blocked_parts = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}

    async def apply(
        self,
        workspace: RepositoryWorkspace,
        request: RepositoryModificationRequest,
    ) -> RepositoryModificationResult:
        """Apply a batch of file changes to the workspace repository."""

        applied: list[RepositoryFileModification] = []
        skipped: list[RepositoryFileModification] = []
        errors: list[str] = []

        for modification in request.modifications:
            try:
                path = self._resolve(workspace.repository_path, modification.path)
                if modification.operation == RepositoryFileOperation.DELETE:
                    if not path.exists():
                        skipped.append(modification)
                        continue
                    path.unlink()
                else:
                    if modification.content is None:
                        skipped.append(modification)
                        continue
                    if modification.operation == RepositoryFileOperation.CREATE and path.exists():
                        errors.append(f"Refusing to overwrite existing file for create operation: {modification.path}")
                        continue
                    if modification.operation == RepositoryFileOperation.UPDATE and not path.exists():
                        errors.append(f"Cannot update missing file: {modification.path}")
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(modification.content, encoding="utf-8", newline="\n")
                applied.append(modification)
            except Exception as exc:
                errors.append(f"{modification.path}: {exc}")

        return RepositoryModificationResult(
            applied=tuple(applied),
            skipped=tuple(skipped),
            errors=tuple(errors),
            metadata={
                "requested_count": len(request.modifications),
                "applied_count": len(applied),
                "skipped_count": len(skipped),
            },
        )

    def _resolve(self, repository_path: Path, relative_path: str) -> Path:
        raw_path = Path(relative_path)
        if raw_path.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        if any(part in {"", ".", ".."} for part in raw_path.parts):
            raise ValueError("Path traversal is not allowed.")
        if any(part in self._blocked_parts for part in raw_path.parts):
            raise ValueError("Protected repository paths cannot be modified.")
        resolved = (repository_path / raw_path).resolve()
        try:
            resolved.relative_to(repository_path.resolve())
        except ValueError as exc:
            raise ValueError("File path escapes repository workspace.") from exc
        return resolved
