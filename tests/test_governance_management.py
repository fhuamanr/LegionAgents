from pathlib import Path

import pytest

from core.contracts.governance_management import (
    GovernanceConfigKind,
    GovernanceConfigScope,
    GovernanceConfigUpsert,
    GovernanceRollbackRequest,
)
from core.governance_management import FileGovernanceConfigRepository, GovernanceManagementService


@pytest.mark.asyncio
async def test_governance_management_versions_and_rolls_back() -> None:
    storage = Path.cwd() / "outputs" / "governance_management_tests" / "configs.json"
    if storage.exists():
        storage.unlink()
    service = GovernanceManagementService(repository=FileGovernanceConfigRepository(storage))

    first, first_version, first_reload = await service.save(
        GovernanceConfigUpsert(
            scope=GovernanceConfigScope.GLOBAL,
            kind=GovernanceConfigKind.GRAVITY,
            name="Global Gravity",
            markdown="- Always preserve boundaries.",
            updated_by="admin",
            change_summary="Initial rule.",
        )
    )
    second, second_version, _ = await service.save(
        GovernanceConfigUpsert(
            scope=GovernanceConfigScope.GLOBAL,
            kind=GovernanceConfigKind.GRAVITY,
            name="Global Gravity",
            markdown="- Always preserve boundaries.\n- Always type contracts.",
            updated_by="admin",
            change_summary="Added contract rule.",
        )
    )

    assert first.version == 1
    assert first_version.version == 1
    assert first_reload.status == "applied"
    assert second.version == 2
    assert second_version.version == 2
    assert len(await service.versions(second.id)) == 2

    rolled_back, rollback_version, reload_event = await service.rollback(
        second.id,
        GovernanceRollbackRequest(target_version=1, updated_by="admin"),
    )

    assert rolled_back.version == 3
    assert rollback_version.markdown == "- Always preserve boundaries."
    assert reload_event.status == "applied"
    assert len(await service.reload_history()) == 3


@pytest.mark.asyncio
async def test_governance_management_lists_agent_specific_config() -> None:
    service = GovernanceManagementService()
    await service.save(
        GovernanceConfigUpsert(
            scope=GovernanceConfigScope.AGENT,
            kind=GovernanceConfigKind.QA_POLICY,
            name="QA Policy",
            agent_name="qa",
            markdown="- Capture screenshots.",
            updated_by="qa-lead",
        )
    )

    documents = await service.list(scope=GovernanceConfigScope.AGENT, agent_name="qa")

    assert len(documents) == 1
    assert documents[0].kind == GovernanceConfigKind.QA_POLICY
