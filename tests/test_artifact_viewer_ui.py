from pathlib import Path


def test_executions_page_renders_workflow_artifacts_panel() -> None:
    page = Path("frontend/app/dashboard/executions/page.tsx").read_text(encoding="utf-8")
    assert "WorkflowArtifactsPanel" in page
    assert "getWorkflowArtifacts" in page


def test_workflow_artifacts_panel_shows_saved_path_hint() -> None:
    panel = Path("frontend/features/executions/workflow-artifacts-panel.tsx").read_text(encoding="utf-8")
    assert "Artifacts saved at data/artifacts/" in panel
    assert "relativePath" in panel
