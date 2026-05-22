import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from core.contracts.repository import (
    BranchCreationRequest,
    CommitGenerationRequest,
    RepositoryCloneRequest,
)
from core.repository import (
    GitCommandPolicy,
    GitHubRepositoryProvider,
    IsolatedWorkspaceManager,
    RepositoryRuntime,
)


@pytest.mark.asyncio
async def test_repository_runtime_clones_branches_analyzes_diff_and_prepares_pr() -> None:
    source_repo = _create_source_repository()
    workspace_manager = IsolatedWorkspaceManager(Path.cwd() / "outputs" / "repository_engine_tests" / "workspaces")
    runtime = RepositoryRuntime(workspace_manager=workspace_manager)

    clone_result = await runtime.clone_repository(
        RepositoryCloneRequest(
            repository_url=str(source_repo),
            agent_name="developer",
            branch="main",
            depth=None,
            thread_id="thread-123",
        )
    )

    assert clone_result.git_results[0].succeeded is True
    assert clone_result.workspace.repository_path.exists()
    assert clone_result.summary is not None
    assert "python" in clone_result.summary.metadata.detected_languages

    branch_result = await runtime.create_branch(
        clone_result.workspace,
        BranchCreationRequest(branch_name="feature/repository-runtime"),
    )

    assert branch_result.git_results[0].succeeded is True

    changed_file = clone_result.workspace.repository_path / "src" / "app.py"
    changed_file.write_text("def hello() -> str:\n    return 'hello repository runtime'\n", encoding="utf-8")

    diff = await runtime.analyze_diff(clone_result.workspace)
    assert len(diff.files) == 1
    assert diff.files[0].path == "src/app.py"
    assert diff.files[0].additions > 0

    message = runtime.generate_commit_message(diff, prefix="Implement repository runtime")
    commit_result = await runtime.generate_commit(
        clone_result.workspace,
        CommitGenerationRequest(message=message),
    )

    assert commit_result.git_results[-1].succeeded is True

    pr = await runtime.prepare_pull_request(
        clone_result.workspace,
        title="Implement repository runtime",
        target_branch="main",
        base_ref="main",
        target_ref="HEAD",
    )

    assert pr.source_branch == "feature/repository-runtime"
    assert pr.target_branch == "main"
    assert "files changed" in pr.description


def test_git_command_policy_blocks_shell_operators() -> None:
    policy = GitCommandPolicy(Path.cwd())

    with pytest.raises(ValueError):
        policy.validate_command(("status", "&&", "whoami"))


@pytest.mark.asyncio
async def test_future_github_provider_boundary_is_explicit() -> None:
    provider = GitHubRepositoryProvider()

    with pytest.raises(NotImplementedError):
        await provider.prepare_remote_pull_request(None)  # type: ignore[arg-type]


def _create_source_repository() -> Path:
    root = Path.cwd() / "outputs" / "repository_engine_tests" / "sources" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Source Repository\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text("def test_hello() -> None:\n    assert True\n", encoding="utf-8")

    _git(root, "init", "-b", "main")
    _git(root, "add", "--all")
    _git(
        root,
        "-c",
        "user.name=Repository Test",
        "-c",
        "user.email=repository-test@example.local",
        "commit",
        "-m",
        "Initial commit",
    )
    return root


def _git(cwd: Path, *args: str) -> None:
    result = subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
