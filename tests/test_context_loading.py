from pathlib import Path

import pytest

from core.context import FileSystemAgentContextLoader
from core.contracts.context import (
    ContextLoadRequest,
    ContextSectionName,
)


@pytest.mark.asyncio
async def test_context_loader_groups_agent_files_by_canonical_sections() -> None:
    loader = FileSystemAgentContextLoader()

    result = await loader.load_request(
        ContextLoadRequest(
            agent_name="developer",
            root_path=Path.cwd() / "agents" / "developer",
        )
    )

    section_names = [section.name for section in result.context.sections]

    assert ContextSectionName.GRAVITY_RULES in section_names
    assert ContextSectionName.ARCHITECTURE_CONSTRAINTS in section_names
    assert ContextSectionName.STANDARDS in section_names
    assert result.context.metadata["document_count"] > 0


@pytest.mark.asyncio
async def test_context_loader_can_filter_sections() -> None:
    loader = FileSystemAgentContextLoader()

    result = await loader.load_request(
        ContextLoadRequest(
            agent_name="ba",
            root_path=Path.cwd() / "agents" / "ba",
            include_sections=(ContextSectionName.GRAVITY_RULES,),
        )
    )

    assert [section.name for section in result.context.sections] == [
        ContextSectionName.GRAVITY_RULES
    ]
    assert "SIEMPRE generar historias INVEST" in result.context.render()
    assert "NUNCA asumir" not in result.context.render()


@pytest.mark.asyncio
async def test_context_loader_reports_missing_context_root() -> None:
    loader = FileSystemAgentContextLoader()

    result = await loader.load_request(
        ContextLoadRequest(
            agent_name="missing",
            root_path=Path.cwd() / "agents" / "missing",
        )
    )

    assert result.context.agent_name == "missing"
    assert result.context.sections == tuple()
    assert result.warnings
