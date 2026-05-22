from pathlib import Path
from uuid import uuid4

import pytest

from core.contracts.pr_review import MergeReadiness, PRReviewCategory, PRReviewRequest
from core.contracts.repository import DiffAnalysis, DiffFileChange, RepositoryChangeKind
from core.contracts.repository_intelligence import (
    ArchitectureDetection,
    RepositoryArchitecturePattern,
    RepositoryGraph,
    RepositoryIntelligenceReport,
    RepositoryIntelligenceSummary,
    RepositoryScanRequest,
)
from core.pr_review import PRAnalysisEngine


@pytest.mark.asyncio
async def test_pr_review_blocks_security_and_missing_tests() -> None:
    root = _workspace()
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "app" / "auth.py").write_text(
        "API_KEY = 'secret'\npassword='hardcoded'\n",
        encoding="utf-8",
    )
    diff = DiffAnalysis(
        files=(
            DiffFileChange(
                path="app/auth.py",
                kind=RepositoryChangeKind.MODIFIED,
                additions=12,
                language="python",
            ),
        ),
        risk_flags=("security_sensitive_files_changed",),
        metadata={"total_additions": 12, "total_deletions": 0},
    )

    report = await PRAnalysisEngine().analyze(
        PRReviewRequest(
            diff=diff,
            repository_root=root,
            title="Update auth handling",
        )
    )

    categories = {comment.category for comment in report.comments}
    assert report.score.readiness == MergeReadiness.BLOCKED
    assert PRReviewCategory.SECURITY in categories
    assert PRReviewCategory.QA in categories
    assert report.score.blocking_count >= 2
    assert any(comment.rule_id == "security.secret-marker" for comment in report.comments)


@pytest.mark.asyncio
async def test_pr_review_scores_clean_tested_documented_pr_as_ready() -> None:
    root = _workspace()
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src" / "service.py").write_text(
        "async def load_user(user_id: str) -> dict[str, str]:\n    return {'id': user_id}\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_service.py").write_text("def test_service() -> None:\n    assert True\n", encoding="utf-8")
    (root / "docs" / "service.md").write_text("# Service\n", encoding="utf-8")
    diff = DiffAnalysis(
        files=(
            DiffFileChange(path="src/service.py", kind=RepositoryChangeKind.MODIFIED, additions=4, language="python"),
            DiffFileChange(path="tests/test_service.py", kind=RepositoryChangeKind.ADDED, additions=3, language="python"),
            DiffFileChange(path="docs/service.md", kind=RepositoryChangeKind.ADDED, additions=2, language="markdown"),
        ),
        metadata={"total_additions": 9, "total_deletions": 0},
    )

    report = await PRAnalysisEngine().analyze(PRReviewRequest(diff=diff, repository_root=root))

    assert report.score.readiness == MergeReadiness.READY
    assert report.score.score >= 95
    assert not report.comments


@pytest.mark.asyncio
async def test_pr_review_architecture_validator_requires_tests_for_contract_changes() -> None:
    root = _workspace()
    (root / "core" / "contracts").mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "core" / "contracts" / "orders.py").write_text("from pydantic import BaseModel\n", encoding="utf-8")
    (root / "app" / "orders.py").write_text("def route() -> None:\n    return None\n", encoding="utf-8")
    diff = DiffAnalysis(
        files=(
            DiffFileChange(path="core/contracts/orders.py", kind=RepositoryChangeKind.MODIFIED, additions=8, language="python"),
            DiffFileChange(path="app/orders.py", kind=RepositoryChangeKind.MODIFIED, additions=4, language="python"),
        ),
        metadata={"total_additions": 12, "total_deletions": 0},
    )

    report = await PRAnalysisEngine().analyze(
        PRReviewRequest(
            diff=diff,
            repository_root=root,
            repository_intelligence=_clean_architecture_report(root),
        )
    )

    assert report.score.readiness == MergeReadiness.BLOCKED
    assert any(comment.rule_id == "architecture.contract-tests-required" for comment in report.comments)
    assert any(comment.rule_id == "architecture.layer-boundary-review" for comment in report.comments)


def _workspace() -> Path:
    root = Path.cwd() / "outputs" / "pr_review_tests" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    return root


def _clean_architecture_report(root: Path) -> RepositoryIntelligenceReport:
    request = RepositoryScanRequest(root_path=root)
    return RepositoryIntelligenceReport(
        request=request,
        root_path=root,
        architecture=(
            ArchitectureDetection(
                pattern=RepositoryArchitecturePattern.CLEAN_ARCHITECTURE,
                confidence=0.9,
                evidence=("core/", "app/"),
            ),
        ),
        graph=RepositoryGraph(),
        summary=RepositoryIntelligenceSummary(
            title="Repository Intelligence Summary",
            overview="Clean architecture repository.",
            detected_patterns=(RepositoryArchitecturePattern.CLEAN_ARCHITECTURE,),
        ),
    )
