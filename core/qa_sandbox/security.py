"""Security boundaries for QA sandbox execution."""

from pathlib import Path


class SandboxSecurityPolicy:
    """Path isolation policy for sandbox artifacts and browser profiles."""

    def __init__(self, sandbox_root: Path) -> None:
        self._sandbox_root = sandbox_root.resolve()

    @property
    def sandbox_root(self) -> Path:
        """Sandbox root path."""

        return self._sandbox_root

    def validate_path(self, path: Path) -> Path:
        """Validate that a path stays within the sandbox root."""

        resolved = path.resolve()
        try:
            resolved.relative_to(self._sandbox_root)
        except ValueError as exc:
            raise ValueError(f"Path escapes sandbox root: {resolved}") from exc
        return resolved

    def safe_name(self, value: str) -> str:
        """Return a filesystem-safe name."""

        safe = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in value)
        return safe.strip(".-") or "artifact"
