"""Autonomous repository runtime."""

from pathlib import Path

from core.contracts.repository import (
    BranchCreationRequest,
    CommitGenerationRequest,
    DiffAnalysis,
    PullRequestPreparation,
    RepositoryFileModification,
    RepositoryFileOperation,
    RepositoryModificationRequest,
    RepositoryModificationResult,
    RepositoryCloneRequest,
    RepositoryRuntimeResult,
    RepositoryWorkspace,
)
from core.repository.diff import DiffAnalyzer
from core.repository.files import RepositoryFileModificationEngine
from core.repository.git import GitService
from core.repository.metadata import RepositorySummarizer
from core.repository.workspace import IsolatedWorkspaceManager
from core.contracts.outputs import DeveloperOutput


class RepositoryRuntime:
    """High-level repository runtime for Developer, QA, and Docs agents."""

    def __init__(
        self,
        workspace_manager: IsolatedWorkspaceManager | None = None,
        git: GitService | None = None,
        summarizer: RepositorySummarizer | None = None,
        diff_analyzer: DiffAnalyzer | None = None,
        file_engine: RepositoryFileModificationEngine | None = None,
    ) -> None:
        self._workspace_manager = workspace_manager or IsolatedWorkspaceManager()
        self._git = git or GitService()
        self._summarizer = summarizer or RepositorySummarizer(self._git)
        self._diff_analyzer = diff_analyzer or DiffAnalyzer(self._git)
        self._file_engine = file_engine or RepositoryFileModificationEngine()

    async def clone_repository(self, request: RepositoryCloneRequest) -> RepositoryRuntimeResult:
        """Clone a repository into an isolated workspace and summarize it."""

        workspace = await self._workspace_manager.create_workspace(
            agent_name=request.agent_name,
            thread_id=request.thread_id,
            repository_name=self._repository_name(request.repository_url),
        )
        clone_result = await self._git.clone(request, workspace)
        summary = await self._summarizer.summarize(workspace) if clone_result.succeeded else None
        return RepositoryRuntimeResult(
            workspace=workspace,
            metadata=summary.metadata if summary else None,
            summary=summary,
            git_results=(clone_result,),
        )

    async def create_branch(
        self,
        workspace: RepositoryWorkspace,
        request: BranchCreationRequest,
    ) -> RepositoryRuntimeResult:
        """Create a branch in an isolated workspace."""

        result = await self._git.create_branch(workspace, request)
        summary = await self._summarizer.summarize(workspace) if result.succeeded else None
        return RepositoryRuntimeResult(
            workspace=workspace,
            metadata=summary.metadata if summary else None,
            summary=summary,
            git_results=(result,),
        )

    async def analyze_diff(
        self,
        workspace: RepositoryWorkspace,
        base_ref: str | None = None,
        target_ref: str | None = None,
    ) -> DiffAnalysis:
        """Analyze a workspace diff."""

        return await self._diff_analyzer.analyze(workspace, base_ref=base_ref, target_ref=target_ref)

    async def apply_file_modifications(
        self,
        workspace: RepositoryWorkspace,
        request: RepositoryModificationRequest,
    ) -> RepositoryRuntimeResult:
        """Apply concrete file modifications and analyze the resulting diff."""

        modifications = await self._file_engine.apply(workspace, request)
        diff = await self._diff_analyzer.analyze(workspace)
        summary = await self._summarizer.summarize(workspace)
        return RepositoryRuntimeResult(
            workspace=workspace,
            metadata=summary.metadata,
            summary=summary,
            diff=diff,
            modifications=modifications,
        )

    async def apply_developer_output(
        self,
        workspace: RepositoryWorkspace,
        output: DeveloperOutput,
    ) -> RepositoryRuntimeResult:
        """Apply developer-generated code and test content to real files."""

        modifications: list[RepositoryFileModification] = []
        for change in output.code_changes:
            if change.content is None:
                continue
            operation = self._operation_from_change_type(change.change_type)
            modifications.append(
                RepositoryFileModification(
                    path=change.path,
                    operation=operation,
                    content=change.content,
                    metadata={"source": "developer.code_changes", "description": change.description},
                )
            )
        for test in output.tests:
            if test.content is None:
                continue
            modifications.append(
                RepositoryFileModification(
                    path=test.path,
                    operation=RepositoryFileOperation.UPSERT,
                    content=test.content,
                    metadata={"source": "developer.tests", "description": test.description, "test_type": test.test_type},
                )
            )
        return await self.apply_file_modifications(
            workspace,
            RepositoryModificationRequest(
                modifications=tuple(modifications),
                metadata={"source": "developer_output", "structured_output_id": str(output.id)},
            ),
        )

    async def generate_commit(
        self,
        workspace: RepositoryWorkspace,
        request: CommitGenerationRequest,
    ) -> RepositoryRuntimeResult:
        """Generate a commit for current workspace changes."""

        results = await self._git.commit(workspace, request)
        summary = await self._summarizer.summarize(workspace)
        diff = await self._diff_analyzer.analyze(workspace)
        return RepositoryRuntimeResult(
            workspace=workspace,
            metadata=summary.metadata,
            summary=summary,
            diff=diff,
            git_results=results,
        )

    async def summarize_repository(self, workspace: RepositoryWorkspace) -> RepositoryRuntimeResult:
        """Summarize a workspace for agent context."""

        summary = await self._summarizer.summarize(workspace)
        return RepositoryRuntimeResult(
            workspace=workspace,
            metadata=summary.metadata,
            summary=summary,
        )

    async def prepare_pull_request(
        self,
        workspace: RepositoryWorkspace,
        title: str,
        target_branch: str,
        description: str | None = None,
        base_ref: str | None = None,
        target_ref: str | None = None,
    ) -> PullRequestPreparation:
        """Prepare provider-neutral pull request metadata."""

        source_branch = await self._git.current_branch(workspace) or "HEAD"
        diff = await self._diff_analyzer.analyze(workspace, base_ref=base_ref, target_ref=target_ref)
        return PullRequestPreparation(
            title=title,
            description=description or self._default_pr_description(diff),
            source_branch=source_branch,
            target_branch=target_branch,
            diff=diff,
            metadata={"workspace_id": str(workspace.id), "agent_name": workspace.agent_name},
        )

    def generate_commit_message(self, diff: DiffAnalysis, prefix: str = "Update repository changes") -> str:
        """Generate a deterministic commit message from a diff."""

        if not diff.files:
            return prefix
        languages = sorted({change.language for change in diff.files if change.language})
        scope = ", ".join(languages) if languages else "files"
        return f"{prefix}: {len(diff.files)} {scope} files"

    def _operation_from_change_type(self, change_type: str) -> RepositoryFileOperation:
        normalized = change_type.lower().strip()
        if normalized in {"create", "add", "new"}:
            return RepositoryFileOperation.CREATE
        if normalized in {"update", "modify", "edit", "refactor"}:
            return RepositoryFileOperation.UPSERT
        if normalized in {"delete", "remove"}:
            return RepositoryFileOperation.DELETE
        return RepositoryFileOperation.UPSERT

    def _default_pr_description(self, diff: DiffAnalysis) -> str:
        flags = "\n".join(f"- {flag}" for flag in diff.risk_flags) or "- No risk flags detected."
        return f"{diff.summary}\n\nRisk flags:\n{flags}"

    def _repository_name(self, repository_url: str) -> str:
        return Path(repository_url.rstrip("/")).stem.replace(".git", "") or "repository"
