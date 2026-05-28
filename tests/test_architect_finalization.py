from pathlib import Path
from uuid import uuid4

from app.services.execution_service import ExecutionService


def test_architect_finalization_repairs_missing_sections_and_builds_index() -> None:
    service = ExecutionService()
    architect_root = Path("outputs") / f"architect-finalization-{uuid4()}" / "architect"
    architect_root.mkdir(parents=True, exist_ok=True)
    (architect_root / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    (architect_root / "api_contracts.md").write_text("# API Contracts\n", encoding="utf-8")
    (architect_root / "database_design.md").write_text("# Database Design\n", encoding="utf-8")

    service._finalize_architect_artifacts(architect_root)

    assert (architect_root / "module_decomposition.md").exists()
    assert (architect_root / "bounded_contexts.md").exists()
    assert (architect_root / "openapi_draft.yaml").exists()
    assert (architect_root / "frontend_architecture.md").exists()
    assert (architect_root / "backend_architecture.md").exists()
    assert (architect_root / "developer_handoff.md").exists()
    assert (architect_root / "architect_artifact_index.json").exists()
    assert (architect_root / "architect_quality_report.md").exists()
    assert (architect_root / "diagrams" / "system_context.mmd").exists()
    assert (architect_root / "adr" / "0001-architecture-style.md").exists()


def test_architect_quality_report_includes_completeness_scores() -> None:
    service = ExecutionService()
    architect_root = Path("outputs") / f"architect-finalization-{uuid4()}" / "architect"
    architect_root.mkdir(parents=True, exist_ok=True)

    service._finalize_architect_artifacts(architect_root)
    report = (architect_root / "architect_quality_report.md").read_text(encoding="utf-8").lower()
    assert "module completeness" in report
    assert "api completeness" in report
    assert "db completeness" in report
    assert "deployment readiness" in report
    assert "depth warnings" in report


def test_architect_quality_score_penalizes_shallow_content() -> None:
    service = ExecutionService()
    architect_root = Path("outputs") / f"architect-finalization-{uuid4()}" / "architect"
    architect_root.mkdir(parents=True, exist_ok=True)
    (architect_root / "architecture.md").write_text("# Architecture\n\nok\n", encoding="utf-8")
    (architect_root / "backend_architecture.md").write_text("# Backend Architecture\n\nthin\n", encoding="utf-8")
    (architect_root / "openapi_draft.yaml").write_text("openapi: 3.0.3\npaths: {}\n", encoding="utf-8")
    (architect_root / "database_design.md").write_text("# Database Design\n\nusers only\n", encoding="utf-8")
    (architect_root / "observability_plan.md").write_text("# Observability Plan\n\nlogs\n", encoding="utf-8")
    (architect_root / "deployment_architecture.md").write_text("# Deployment Architecture\n\ndocker\n", encoding="utf-8")
    (architect_root / "developer_handoff.md").write_text("# Developer Handoff\n\nshort\n", encoding="utf-8")

    service._finalize_architect_artifacts(architect_root)
    report = (architect_root / "architect_quality_report.md").read_text(encoding="utf-8").lower()
    assert "depth is low" in report
    assert "developer handoff readiness" in report
