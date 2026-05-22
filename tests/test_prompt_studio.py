import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.contracts.prompt_studio import (
    PromptPreviewRequest,
    PromptRollbackRequest,
    PromptScope,
    PromptTestRequest,
    PromptUpsert,
    PromptVariable,
)
from core.prompt_studio import PromptStudioService


@pytest.mark.asyncio
async def test_prompt_studio_versions_preview_test_compare_and_rollback() -> None:
    service = PromptStudioService()

    prompt, version = await service.save(
        PromptUpsert(
            name="Developer Implementation Prompt",
            scope=PromptScope.AGENT,
            agent_name="developer",
            markdown="# Task\nBuild {{feature}} using {{standard}}.",
            variables=(
                PromptVariable(name="feature", description="Feature name"),
                PromptVariable(name="standard", default="Clean Architecture"),
            ),
            updated_by="lead",
        )
    )
    updated, updated_version = await service.save(
        PromptUpsert(
            name="Developer Implementation Prompt",
            scope=PromptScope.AGENT,
            agent_name="developer",
            markdown="# Task\nBuild {{feature}} using {{standard}}.\n# Output\nReturn tests.",
            variables=prompt.variables,
            updated_by="lead",
        )
    )

    preview = await service.preview(
        PromptPreviewRequest(
            markdown=updated.markdown,
            variables={"feature": "checkout", "standard": "Clean Architecture"},
        )
    )
    test = await service.test(
        PromptTestRequest(
            prompt_id=updated.id,
            variables={"feature": "checkout", "standard": "Clean Architecture"},
            test_input="Generate a plan.",
            expected_output="tests",
        )
    )
    comparison = await service.compare_versions(updated.id, version.version, updated_version.version)
    rolled_back, rollback_version = await service.rollback(
        updated.id,
        request=PromptRollbackRequest(
            target_version=1,
            updated_by="lead",
        ),
    )

    assert preview.rendered.startswith("# Task")
    assert preview.missing_variables == tuple()
    assert test.evaluation.passed is True
    assert comparison.changed_line_count > 0
    assert rolled_back.markdown == prompt.markdown
    assert rollback_version.version == 3


def test_prompt_studio_api_supports_management_testing_and_comparison() -> None:
    client = TestClient(create_app())

    created = client.post(
        "/prompt-studio/prompts",
        json={
            "name": "QA Browser Prompt",
            "scope": "agent",
            "agent_name": "qa",
            "markdown": "# QA\nValidate {{flow}}.",
            "variables": [{"name": "flow", "description": "User flow"}],
            "updated_by": "qa-lead",
        },
    )
    assert created.status_code == 201
    prompt_id = created.json()["prompt"]["id"]

    updated = client.post(
        "/prompt-studio/prompts",
        json={
            "name": "QA Browser Prompt",
            "scope": "agent",
            "agent_name": "qa",
            "markdown": "# QA\nValidate {{flow}}.\nCapture screenshots.",
            "variables": [{"name": "flow"}],
            "updated_by": "qa-lead",
        },
    )
    assert updated.status_code == 201

    preview = client.post(
        "/prompt-studio/prompts/preview",
        json={"markdown": "# QA\nValidate {{flow}}.", "variables": {"flow": "checkout"}},
    )
    assert preview.status_code == 200
    assert preview.json()["preview"]["rendered"] == "# QA\nValidate checkout."

    result = client.post(
        "/prompt-studio/prompts/test",
        json={"prompt_id": prompt_id, "variables": {"flow": "checkout"}, "test_input": "Run smoke test."},
    )
    assert result.status_code == 200
    assert result.json()["result"]["evaluation"]["score"] > 0

    versions = client.get(f"/prompt-studio/prompts/{prompt_id}/versions")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) == 2

    comparison = client.get(f"/prompt-studio/prompts/{prompt_id}/compare?left_version=1&right_version=2")
    assert comparison.status_code == 200
    assert comparison.json()["comparison"]["changed_line_count"] > 0

    rollback = client.post(
        f"/prompt-studio/prompts/{prompt_id}/rollback",
        json={"target_version": 1, "updated_by": "qa-lead"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["prompt"]["version"] == 3
