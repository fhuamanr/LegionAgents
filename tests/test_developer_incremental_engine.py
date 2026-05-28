from pathlib import Path
from uuid import uuid4

import pytest

from app.services.execution_service import ExecutionService
from core.agents.llm_runtime import DeveloperRepositoryAgentRuntime
from core.agents.runtime import AgentModelClient
from core.runtime.models import RuntimeAgentConfig


class _FakeClient(AgentModelClient):
    async def complete(self, messages):
        return "{}"


def _build_runtime() -> DeveloperRepositoryAgentRuntime:
    return DeveloperRepositoryAgentRuntime(
        config=RuntimeAgentConfig(
            name="developer",
            role="software developer",
            context_path=Path.cwd() / "agents" / "developer",
            output_schema_name="DeveloperOutput",
        ),
        model_client=_FakeClient(),
    )


def test_developer_generated_project_bundle_contains_required_artifacts() -> None:
    runtime = _build_runtime()
    bundle = runtime._generated_project_files(  # noqa: SLF001
        {
            "developer_handoff.md": "Implement routes and tests",
            "openapi_draft.yaml": "openapi: 3.0.3",
            "backend_architecture.md": "api/application/domain/infrastructure",
            "frontend_architecture.md": "home/login/catalog/checkout",
            "database_design.md": "users products orders",
        },
        mode="implement_core",
    )
    files = bundle["files"]
    assert "generated_project/docker-compose.yml" in files
    assert "generated_project/.env.example" in files
    assert "generated_project/run_instructions.md" in files
    assert "generated_project/qa_handoff.md" in files
    assert "generated_project/api_implementation_matrix.md" in files
    assert "generated_project/database_implementation_matrix.md" in files
    assert "generated_project/frontend_route_matrix.md" in files
    assert "generated_project/frontend/src/routes/Home.tsx" in files
    assert "generated_project/frontend/src/routes/Checkout.tsx" in files
    assert "generated_project/backend/src/main.py" in files
    assert "generated_project/backend/src/api/routes/checkout.py" in files


@pytest.mark.asyncio
async def test_developer_artifact_persistence_writes_generated_project_tree() -> None:
    service = ExecutionService()
    root = Path("outputs") / f"developer-generated-{uuid4()}" / "developer"
    root.mkdir(parents=True, exist_ok=True)
    structured = {
        "code_changes": [
            {
                "path": "generated_project/frontend/src/routes/Home.tsx",
                "content": "export default function Home(){return null}\n",
            },
            {
                "path": "generated_project/backend/src/main.py",
                "content": "print('ok')\n",
            },
            {
                "path": "generated_project/run_instructions.md",
                "content": "# Run\n",
            },
        ],
        "tests": [
            {
                "path": "generated_project/tests/backend/test_health.py",
                "content": "def test_health(): assert True\n",
            }
        ],
    }
    await service._persist_developer_files(root, structured)  # noqa: SLF001
    assert (root / "generated_project" / "frontend" / "src" / "routes" / "Home.tsx").exists()
    assert (root / "generated_project" / "backend" / "src" / "main.py").exists()
    assert (root / "generated_project" / "run_instructions.md").exists()
    assert (root / "generated_project" / "tests" / "backend" / "test_health.py").exists()
    assert (root / "patch.diff").exists()

