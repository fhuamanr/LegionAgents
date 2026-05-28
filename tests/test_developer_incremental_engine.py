from pathlib import Path
from uuid import uuid4

import pytest
import os

from app.services.execution_service import ExecutionService
from core.agents.llm_runtime import DeveloperRepositoryAgentRuntime
from core.agents.runtime import AgentModelClient
from core.runtime.models import RuntimeAgentConfig
from core.contracts.execution import AgentExecutionRequest
from core.contracts.outputs import DeveloperOutput


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


def test_developer_requires_non_empty_architect_inputs() -> None:
    runtime = _build_runtime()
    with pytest.raises(ValueError, match="developer_input_missing_required_architect_artifacts"):
        runtime._validate_required_architect_inputs(  # noqa: SLF001
            {
                "developer_handoff.md": "",
                "openapi_draft.yaml": "openapi: 3.0.3",
                "backend_architecture.md": "a",
            }
        )


def test_developer_resolves_architect_inputs_from_filesystem_and_index() -> None:
    runtime = _build_runtime()
    workflow_id = uuid4()
    artifact_root = Path("outputs") / f"developer-input-resolution-{uuid4()}" / "artifacts"
    architect = artifact_root / str(workflow_id) / "architect"
    (architect / "api").mkdir(parents=True, exist_ok=True)
    (architect / "backend").mkdir(parents=True, exist_ok=True)
    (architect / "frontend").mkdir(parents=True, exist_ok=True)
    (architect / "database").mkdir(parents=True, exist_ok=True)
    (architect / "handoff").mkdir(parents=True, exist_ok=True)
    (architect / "architecture").mkdir(parents=True, exist_ok=True)
    (architect / "api" / "openapi_draft.yaml").write_text("openapi: 3.0.3\ncomponents:\n  schemas:\n", encoding="utf-8")
    (architect / "backend" / "backend_architecture.md").write_text("backend architecture detailed content", encoding="utf-8")
    (architect / "frontend" / "frontend_architecture.md").write_text("frontend architecture detailed content", encoding="utf-8")
    (architect / "database" / "database_design.md").write_text("database design detailed content", encoding="utf-8")
    (architect / "api" / "api_contracts.md").write_text("api contracts detailed content", encoding="utf-8")
    (architect / "handoff" / "developer_handoff.md").write_text("developer handoff detailed content", encoding="utf-8")
    (architect / "architecture" / "module_decomposition.md").write_text("module decomposition detailed content", encoding="utf-8")
    (architect / "architect_artifact_index.json").write_text(
        "{\n"
        '  "artifacts": [\n'
        '    {"name":"developer_handoff.md","path":"architect/handoff/developer_handoff.md"},\n'
        '    {"name":"openapi_draft.yaml","path":"architect/api/openapi_draft.yaml"},\n'
        '    {"name":"backend_architecture.md","path":"architect/backend/backend_architecture.md"},\n'
        '    {"name":"frontend_architecture.md","path":"architect/frontend/frontend_architecture.md"},\n'
        '    {"name":"database_design.md","path":"architect/database/database_design.md"},\n'
        '    {"name":"api_contracts.md","path":"architect/api/api_contracts.md"},\n'
        '    {"name":"module_decomposition.md","path":"architect/architecture/module_decomposition.md"}\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    os.environ["ARTIFACT_ROOT"] = str(artifact_root)
    request = AgentExecutionRequest(
        workflow_id=workflow_id,
        execution_id=uuid4(),
        agent_name="developer",
        task="Implement project",
        upstream_artifacts=tuple(),
        metadata={},
    )
    resolved, report, missing = runtime._resolve_architect_inputs(request)  # noqa: SLF001
    assert not missing
    assert report["source_index_used"] is True
    assert "developer_handoff.md" in resolved and resolved["developer_handoff.md"]
    assert "openapi_draft.yaml" in resolved and resolved["openapi_draft.yaml"]


def test_developer_auto_repairs_real_secret_values() -> None:
    runtime = _build_runtime()
    output = DeveloperOutput.model_validate(
        {
            "agent_name": "developer",
            "summary": "test",
            "code_changes": [
                {
                    "path": "generated_project/.env",
                    "change_type": "create",
                    "description": "env",
                    "content": "DATABASE_PASSWORD=myRealPass123\nAPI_KEY=sk-live-abcde12345\n",
                }
            ],
            "tests": [],
        }
    )
    repaired, report = runtime._auto_repair_governance_secrets(output)  # noqa: SLF001
    assert report["repair_applied"] is True
    content = repaired.model_dump(mode="json")["code_changes"][0]["content"]
    assert "<your-password>" in content
    assert "<your-api-key>" in content


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
