"""Security policy for repository command execution."""

from pathlib import Path


class GitCommandPolicy:
    """Allowlist and path isolation for git commands."""

    _allowed_commands = {
        "add",
        "branch",
        "checkout",
        "clone",
        "commit",
        "config",
        "diff",
        "init",
        "log",
        "rev-parse",
        "status",
        "symbolic-ref",
    }

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()

    def validate_command(self, args: tuple[str, ...]) -> None:
        """Validate git command arguments before execution."""

        if not args:
            raise ValueError("Git command cannot be empty.")
        command = self._primary_command(args)
        if command not in self._allowed_commands:
            raise ValueError(f"Git command is not allowed: {command}")
        if any(self._contains_shell_operator(arg) for arg in args):
            raise ValueError("Git command arguments cannot contain shell operators.")

    def validate_cwd(self, cwd: Path) -> Path:
        """Validate command working directory."""

        resolved = cwd.resolve()
        if not self.is_within_workspace(resolved):
            raise ValueError(f"Command cwd escapes workspace root: {resolved}")
        return resolved

    def validate_target_path(self, path: Path) -> Path:
        """Validate a target path stays inside the workspace root."""

        resolved = path.resolve()
        if not self.is_within_workspace(resolved):
            raise ValueError(f"Target path escapes workspace root: {resolved}")
        return resolved

    def is_within_workspace(self, path: Path) -> bool:
        """Return whether a path is inside the workspace root."""

        try:
            path.resolve().relative_to(self._workspace_root)
        except ValueError:
            return False
        return True

    def _contains_shell_operator(self, value: str) -> bool:
        return any(operator in value for operator in ("&&", "||", ";", "|", "`", "$("))

    def _primary_command(self, args: tuple[str, ...]) -> str:
        index = 0
        while index < len(args):
            if args[index] == "-c":
                index += 2
                continue
            return args[index]
        return ""
