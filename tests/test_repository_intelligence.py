from pathlib import Path
from uuid import uuid4

import pytest

from core.contracts.repository_intelligence import (
    RepositoryArchitecturePattern,
    RepositoryIngestionKind,
    RepositoryScanRequest,
)
from core.repository_intelligence import GitHubRepositoryScanner, RepositoryIntelligenceEngine


@pytest.mark.asyncio
async def test_repository_intelligence_detects_frameworks_architecture_and_graph() -> None:
    repo = _create_sample_repository()
    engine = RepositoryIntelligenceEngine()

    report = await engine.analyze(
        RepositoryScanRequest(
            root_path=repo,
            ingestion_kind=RepositoryIngestionKind.LOCAL,
            max_files=200,
        )
    )

    languages = {language.language for language in report.languages}
    frameworks = {framework.name for framework in report.frameworks}
    patterns = {detection.pattern for detection in report.architecture}
    graph_edges = {(edge.source, edge.target) for edge in report.graph.edges}

    assert {"python", "typescript", "json", "yaml"}.issubset(languages)
    assert {"fastapi", "pydantic", "langgraph", "nextjs", "react", "tailwindcss", "docker"}.issubset(frameworks)
    assert RepositoryArchitecturePattern.CLEAN_ARCHITECTURE in patterns
    assert RepositoryArchitecturePattern.FASTAPI_BACKEND in patterns
    assert RepositoryArchitecturePattern.NEXTJS_APP_ROUTER in patterns
    assert ("app/main.py", "app/routers/items.py") in graph_edges
    assert report.graph.metadata["node_count"] >= len(report.files)
    assert "fastapi" in report.summary.primary_frameworks
    assert "Repository uses" in report.summary.overview


@pytest.mark.asyncio
async def test_repository_intelligence_honors_scan_limits() -> None:
    repo = _create_sample_repository()
    engine = RepositoryIntelligenceEngine()

    report = await engine.analyze(
        RepositoryScanRequest(
            root_path=repo,
            ingestion_kind=RepositoryIngestionKind.MOUNTED,
            max_files=3,
        )
    )

    assert len(report.files) == 3
    assert report.request.ingestion_kind is RepositoryIngestionKind.MOUNTED


@pytest.mark.asyncio
async def test_github_repository_scanner_boundary_is_explicit() -> None:
    scanner = GitHubRepositoryScanner()

    with pytest.raises(NotImplementedError):
        await scanner.scan(
            RepositoryScanRequest(
                repository_url="https://github.com/example/repository",
                ingestion_kind=RepositoryIngestionKind.GITHUB,
            )
        )


def _create_sample_repository() -> Path:
    root = Path.cwd() / "outputs" / "repository_intelligence_tests" / str(uuid4())
    (root / "app" / "routers").mkdir(parents=True, exist_ok=True)
    (root / "core" / "contracts").mkdir(parents=True, exist_ok=True)
    (root / "core" / "graph").mkdir(parents=True, exist_ok=True)
    (root / "frontend" / "app").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)

    (root / "requirements.txt").write_text(
        "fastapi>=0.111\npydantic>=2.7\nlanggraph>=0.2\npytest>=8.2\n",
        encoding="utf-8",
    )
    (root / "docker-compose.yml").write_text("services:\n  backend:\n    build: .\n", encoding="utf-8")
    (root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\nfrom app.routers.items import router\n\napp = FastAPI()\napp.include_router(router)\n",
        encoding="utf-8",
    )
    (root / "app" / "routers" / "items.py").write_text(
        "from fastapi import APIRouter\nfrom core.contracts.items import Item\n\nrouter = APIRouter()\n",
        encoding="utf-8",
    )
    (root / "core" / "contracts" / "items.py").write_text(
        "from pydantic import BaseModel\n\nclass Item(BaseModel):\n    name: str\n",
        encoding="utf-8",
    )
    (root / "core" / "graph" / "workflow.py").write_text(
        "from langgraph.graph import StateGraph\n",
        encoding="utf-8",
    )
    (root / "frontend" / "package.json").write_text(
        """
{
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "tailwindcss": "4.0.0"
  }
}
""".strip(),
        encoding="utf-8",
    )
    (root / "frontend" / "app" / "page.tsx").write_text(
        "import React from 'react';\nexport default function Page() { return <main />; }\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_items.py").write_text(
        "from app.main import app\n\ndef test_app_exists() -> None:\n    assert app\n",
        encoding="utf-8",
    )
    return root
