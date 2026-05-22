import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from core.agents.llm_runtime import DeveloperRepositoryAgentRuntime
from core.contracts.execution import AgentExecutionRequest
from core.contracts.repository import (
    RepositoryFileModification,
    RepositoryFileOperation,
    RepositoryModificationRequest,
)
from core.repository import IsolatedWorkspaceManager, RepositoryFileModificationEngine, RepositoryRuntime
from core.runtime.models import RuntimeAgentConfig
from tests.test_real_workflow_runtime import WorkflowModelClient


@pytest.mark.asyncio
async def test_file_modification_engine_applies_real_safe_changes() -> None:
    source_repo = _create_source_repository()
    runtime = RepositoryRuntime(
        workspace_manager=IsolatedWorkspaceManager(
            Path.cwd() / "outputs" / "repository_manipulation_tests" / "workspaces"
        )
    )
    clone = await runtime.clone_repository(
        request=_clone_request(source_repo),
    )
    engine = RepositoryFileModificationEngine()

    result = await engine.apply(
        clone.workspace,
        RepositoryModificationRequest(
            modifications=(
                RepositoryFileModification(
                    path="src/new_module.py",
                    operation=RepositoryFileOperation.CREATE,
                    content="def value() -> int:\n    return 42\n",
                ),
            )
        ),
    )

    assert result.succeeded is True
    assert (clone.workspace.repository_path / "src" / "new_module.py").read_text(encoding="utf-8") == (
        "def value() -> int:\n    return 42\n"
    )


@pytest.mark.asyncio
async def test_file_modification_engine_blocks_path_escape() -> None:
    source_repo = _create_source_repository()
    runtime = RepositoryRuntime(
        workspace_manager=IsolatedWorkspaceManager(
            Path.cwd() / "outputs" / "repository_manipulation_tests" / "workspaces"
        )
    )
    clone = await runtime.clone_repository(request=_clone_request(source_repo))

    result = await RepositoryFileModificationEngine().apply(
        clone.workspace,
        RepositoryModificationRequest(
            modifications=(
                RepositoryFileModification(
                    path="../escape.py",
                    content="bad = True\n",
                ),
            )
        ),
    )

    assert result.succeeded is False
    assert "Path traversal" in result.errors[0]


@pytest.mark.asyncio
async def test_developer_agent_modifies_repository_commits_and_prepares_pr() -> None:
    source_repo = _create_source_repository()
    repository_runtime = RepositoryRuntime(
        workspace_manager=IsolatedWorkspaceManager(
            Path.cwd() / "outputs" / "repository_manipulation_tests" / "agent-workspaces"
        )
    )
    agent = DeveloperRepositoryAgentRuntime(
        config=RuntimeAgentConfig(
            name="developer",
            role="software developer",
            context_path=Path.cwd() / "agents" / "developer",
            output_schema_name="DeveloperOutput",
        ),
        model_client=WorkflowModelClient(),
        repository_runtime=repository_runtime,
    )

    result = await agent.execute(
        AgentExecutionRequest(
            agent_name="developer",
            task="Modify the repository and generate tests.",
            metadata={
                "repository_url": str(source_repo),
                "base_branch": "main",
                "target_branch": "main",
                "branch_name": "codex/real-repository-manipulation",
            },
        )
    )

    repository_metadata = result.metadata["repository_manipulation"]
    workspace_path = Path(str(repository_metadata["workspace_path"]))

    assert result.status == "completed"
    assert repository_metadata["modification_count"] == 2
    assert repository_metadata["diff_file_count"] >= 1
    assert repository_metadata["pull_request"]["source_branch"] == "codex/real-repository-manipulation"
    assert (workspace_path / "src" / "app.py").read_text(encoding="utf-8") == (
        "def hello() -> str:\n    return \"hello from developer\"\n"
    )
    assert _git(workspace_path, "log", "--oneline", "-1").stdout.strip()


def _clone_request(source_repo: Path):
    from core.contracts.repository import RepositoryCloneRequest

    return RepositoryCloneRequest(
        repository_url=str(source_repo),
        agent_name="developer",
        branch="main",
        depth=None,
    )


def _create_source_repository() -> Path:
    root = Path.cwd() / "outputs" / "repository_manipulation_tests" / "sources" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "app.py").write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text("def test_hello() -> None:\n    assert True\n", encoding="utf-8")
    _git(root, "init", "-b", "main")
    _git(root, "add", "--all")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial")
    return root


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(("git", *args), cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result
