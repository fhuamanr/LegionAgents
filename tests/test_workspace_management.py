import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.contracts.workspaces import (
    ProjectCreateRequest,
    RepositoryBinding,
    RepositoryBindingProvider,
    WorkspaceCreateRequest,
)
from core.workspaces import WorkspaceManagementService


@pytest.mark.asyncio
async def test_workspace_management_is_tenant_aware_and_isolated() -> None:
    service = WorkspaceManagementService()

    workspace = await service.create_workspace(
        WorkspaceCreateRequest(
            tenant_id="tenant-a",
            name="Payments Platform",
            description="Payment delivery workspace",
            created_by="owner-a",
        )
    )
    await service.create_workspace(
        WorkspaceCreateRequest(
            tenant_id="tenant-b",
            name="Support Platform",
            created_by="owner-b",
        )
    )
    project = await service.create_project(
        workspace.id,
        ProjectCreateRequest(
            name="Checkout",
            repositories=(
                RepositoryBinding(
                    name="checkout-api",
                    provider=RepositoryBindingProvider.GITLAB,
                    uri="https://gitlab.com/example/checkout-api.git",
                ),
            ),
        ),
    )

    tenant_a = await service.list_workspaces("tenant-a")
    isolation = await service.isolation_summary(workspace.id)

    assert len(tenant_a) == 1
    assert tenant_a[0].tenant_id == "tenant-a"
    assert project.repositories[0].provider == RepositoryBindingProvider.GITLAB
    assert isolation.project_count == 1
    assert isolation.repository_count == 1
    assert isolation.memory_namespace.startswith("tenant-a:")
    assert set(isolation.enabled_agents) >= {"ba", "architect", "developer", "qa", "docs", "pr"}


def test_workspace_management_api_creates_projects_and_reports_isolation() -> None:
    client = TestClient(create_app())

    workspace_response = client.post(
        "/workspaces",
        json={
            "tenant_id": "tenant-ui",
            "name": "Retail Workspace",
            "description": "Retail delivery projects",
            "created_by": "retail-admin",
            "agents": [
                {"agent_name": "developer", "enabled": True, "max_retries": 3},
                {"agent_name": "qa", "enabled": True, "prompt_profile": "browser-validation"},
            ],
        },
    )

    assert workspace_response.status_code == 201
    workspace = workspace_response.json()["workspace"]
    workspace_id = workspace["id"]
    assert workspace["configuration"]["memory_namespace"].startswith("tenant-ui:")

    project_response = client.post(
        f"/workspaces/{workspace_id}/projects",
        json={
            "name": "Storefront",
            "repositories": [
                {
                    "name": "storefront-web",
                    "provider": "github",
                    "uri": "https://github.com/example/storefront-web.git",
                    "default_branch": "main",
                }
            ],
        },
    )

    assert project_response.status_code == 201
    assert project_response.json()["project"]["repositories"][0]["provider"] == "github"

    list_response = client.get("/workspaces?tenant_id=tenant-ui")
    projects_response = client.get(f"/workspaces/{workspace_id}/projects")
    isolation_response = client.get(f"/workspaces/{workspace_id}/isolation")

    assert list_response.status_code == 200
    assert len(list_response.json()["workspaces"]) == 1
    assert len(projects_response.json()["projects"]) == 1
    assert isolation_response.json()["isolation"]["repository_count"] == 1
