"""Async git service layer."""

import asyncio
from pathlib import Path

from core.contracts.repository import (
    BranchCreationRequest,
    CommitGenerationRequest,
    GitCommandResult,
    RepositoryCloneRequest,
    RepositoryWorkspace,
)
from core.repository.security import GitCommandPolicy


class GitService:
    """Secure async boundary around the git executable."""

    def __init__(self, executable: str = "git") -> None:
        self._executable = executable

    async def clone(self, request: RepositoryCloneRequest, workspace: RepositoryWorkspace) -> GitCommandResult:
        """Clone a repository into an isolated workspace."""

        GitCommandPolicy(workspace.root_path).validate_target_path(workspace.repository_path)
        args: list[str] = ["clone"]
        if request.depth is not None:
            args.extend(["--depth", str(request.depth)])
        if request.branch:
            args.extend(["--branch", request.branch])
        args.extend([request.repository_url, str(workspace.repository_path)])
        return await self.run(tuple(args), cwd=workspace.root_path)

    async def create_branch(
        self,
        workspace: RepositoryWorkspace,
        request: BranchCreationRequest,
    ) -> GitCommandResult:
        """Create and checkout a branch."""

        args: list[str] = ["checkout", "-B", request.branch_name]
        if request.start_point:
            args.append(request.start_point)
        return await self.run(tuple(args), cwd=workspace.repository_path)

    async def status(self, workspace: RepositoryWorkspace, porcelain: bool = True) -> GitCommandResult:
        """Return repository status."""

        args = ("status", "--porcelain") if porcelain else ("status",)
        return await self.run(args, cwd=workspace.repository_path)

    async def diff(self, workspace: RepositoryWorkspace, *args: str) -> GitCommandResult:
        """Return repository diff."""

        return await self.run(("diff", *args), cwd=workspace.repository_path)

    async def add_all(self, workspace: RepositoryWorkspace) -> GitCommandResult:
        """Stage all workspace changes."""

        return await self.run(("add", "--all"), cwd=workspace.repository_path)

    async def commit(
        self,
        workspace: RepositoryWorkspace,
        request: CommitGenerationRequest,
    ) -> tuple[GitCommandResult, ...]:
        """Generate a commit from current workspace changes."""

        results: list[GitCommandResult] = []
        if request.include_all:
            results.append(await self.add_all(workspace))
        results.append(
            await self.run(
                (
                    "-c",
                    f"user.name={request.author_name}",
                    "-c",
                    f"user.email={request.author_email}",
                    "commit",
                    "-m",
                    request.message,
                ),
                cwd=workspace.repository_path,
            )
        )
        return tuple(results)

    async def current_branch(self, workspace: RepositoryWorkspace) -> str | None:
        """Return current branch name."""

        result = await self.run(("rev-parse", "--abbrev-ref", "HEAD"), cwd=workspace.repository_path)
        return result.stdout.strip() if result.succeeded else None

    async def head_sha(self, workspace: RepositoryWorkspace) -> str | None:
        """Return current HEAD SHA."""

        result = await self.run(("rev-parse", "HEAD"), cwd=workspace.repository_path)
        return result.stdout.strip() if result.succeeded else None

    async def remote_url(self, workspace: RepositoryWorkspace) -> str | None:
        """Return origin remote URL."""

        result = await self.run(("config", "--get", "remote.origin.url"), cwd=workspace.repository_path)
        return result.stdout.strip() if result.succeeded else None

    async def run(self, args: tuple[str, ...], cwd: Path) -> GitCommandResult:
        """Run a secure git command."""

        workspace_root = self._workspace_root_for(cwd)
        policy = GitCommandPolicy(workspace_root)
        policy.validate_command(args)
        resolved_cwd = policy.validate_cwd(cwd)
        process = await asyncio.create_subprocess_exec(
            self._executable,
            *args,
            cwd=resolved_cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return GitCommandResult(
            command=(self._executable, *args),
            cwd=resolved_cwd,
            return_code=process.returncode,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    def _workspace_root_for(self, cwd: Path) -> Path:
        parts = cwd.resolve().parts
        if "outputs" in parts and "repositories" in parts:
            repositories_index = parts.index("repositories")
            if len(parts) > repositories_index + 3:
                return Path(*parts[: repositories_index + 4])
        return cwd.resolve()
