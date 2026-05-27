from pathlib import Path
from uuid import uuid4

from app.services.execution_service import ExecutionService


def test_ba_finalization_repairs_sparse_sections_and_builds_index() -> None:
    service = ExecutionService()
    ba_root = Path("outputs") / f"ba-finalization-{uuid4()}" / "ba"
    ba_root.mkdir(parents=True, exist_ok=True)
    (ba_root / "mvp_page_matrix.md").write_text("# MVP Page Matrix\n\n| Page | Category | Classification |\n|---|---|---|\n", encoding="utf-8")
    (ba_root / "navigation_structure.md").write_text("# Navigation Structure\n\n## Public Navigation\n", encoding="utf-8")
    (ba_root / "application_shell.md").write_text("# Application Shell\n", encoding="utf-8")
    (ba_root / "roadmap_priorities.md").write_text("# Roadmap Priorities\n", encoding="utf-8")
    (ba_root / "frontend_mvp_expectations.md").write_text("# Frontend MVP Expectations\n", encoding="utf-8")
    (ba_root / "domain_entities.md").write_text("## User\n", encoding="utf-8")
    (ba_root / "state_machines.md").write_text("## Cart\n", encoding="utf-8")
    (ba_root / "functional_flows.md").write_text("## Checkout flow\n", encoding="utf-8")
    (ba_root / "validation_rules.md").write_text("- Password rule\n", encoding="utf-8")
    (ba_root / "permissions_matrix.md").write_text("| Actor | Allowed |\n|---|---|\n| Customer | browse |\n", encoding="utf-8")
    (ba_root / "business_events.md").write_text("## order_created\n", encoding="utf-8")
    (ba_root / "user_lifecycle.md").write_text("session lifecycle\n", encoding="utf-8")

    service._finalize_ba_artifacts(ba_root)

    assert (ba_root / "artifact_completeness_report.md").exists()
    assert (ba_root / "ba_artifact_index.json").exists()
    assert (ba_root / "ba_quality_report.md").exists()
    matrix = (ba_root / "mvp_page_matrix.md").read_text(encoding="utf-8")
    assert "Home" in matrix
    assert "Dashboard" in matrix
    nav = (ba_root / "navigation_structure.md").read_text(encoding="utf-8")
    assert "Public Navigation" in nav
    assert "Authenticated Navigation" in nav


def test_ba_quality_alignment_does_not_false_flag_core_pages() -> None:
    service = ExecutionService()
    ba_root = Path("outputs") / f"ba-finalization-{uuid4()}" / "ba"
    ba_root.mkdir(parents=True, exist_ok=True)
    (ba_root / "mvp_page_matrix.md").write_text(
        "\n".join(
            [
                "# MVP Page Matrix",
                "| Page | Category | Classification |",
                "|---|---|---|",
                "| Home | PUBLIC | Core MVP |",
                "| Dashboard | AUTH | Core MVP |",
                "| Profile | AUTH | Core MVP |",
                "| Settings | AUTH | Core MVP |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ba_root / "navigation_structure.md").write_text("# Navigation Structure\n- Home\n- Dashboard\n- Profile\n- Settings\n", encoding="utf-8")
    (ba_root / "application_shell.md").write_text("Routing hierarchy includes Home Dashboard Profile Settings", encoding="utf-8")
    (ba_root / "roadmap_priorities.md").write_text("## Core MVP\n- Home\n- Dashboard\n- Profile\n- Settings\n", encoding="utf-8")
    (ba_root / "frontend_mvp_expectations.md").write_text("session persistence", encoding="utf-8")
    (ba_root / "domain_entities.md").write_text("## User\n## Product\n## Order\n", encoding="utf-8")
    (ba_root / "state_machines.md").write_text("## Cart\n## Order\n", encoding="utf-8")
    (ba_root / "functional_flows.md").write_text("## Checkout flow\n", encoding="utf-8")
    (ba_root / "validation_rules.md").write_text("- Password rule\n- Stock rule\n- Payment rule\n", encoding="utf-8")
    (ba_root / "permissions_matrix.md").write_text("| Actor | Allowed |\n|---|---|\n| Customer | checkout |\n| Admin | manage |\n", encoding="utf-8")
    (ba_root / "business_events.md").write_text("## order_created\n## payment_failed\n", encoding="utf-8")
    (ba_root / "user_lifecycle.md").write_text("session lifecycle and onboarding", encoding="utf-8")

    service._finalize_ba_artifacts(ba_root)
    report = (ba_root / "ba_quality_report.md").read_text(encoding="utf-8").lower()
    assert "missing home/landing" not in report
    assert "missing dashboard" not in report
    assert "missing profile" not in report
    assert "missing settings" not in report
