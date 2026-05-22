"""Framework and platform detection."""

import json
from pathlib import Path

from core.contracts.repository_intelligence import FrameworkDetection, RepositoryFileIndex


class FrameworkDetector:
    """Detects frameworks using manifests, config files, and lightweight source evidence."""

    async def detect(self, root_path: Path, files: tuple[RepositoryFileIndex, ...]) -> tuple[FrameworkDetection, ...]:
        """Detect framework footprints in a scanned repository."""

        evidence: dict[str, set[str]] = {}
        file_paths = {file.path for file in files}

        self._detect_by_path(file_paths, evidence)
        await self._detect_python(root_path, files, evidence)
        await self._detect_node(root_path, files, evidence)

        return tuple(
            FrameworkDetection(
                name=name,
                category=self._category(name),
                confidence=self._confidence(name, values),
                evidence=tuple(sorted(values)),
            )
            for name, values in sorted(evidence.items())
        )

    def _detect_by_path(self, file_paths: set[str], evidence: dict[str, set[str]]) -> None:
        if "docker-compose.yml" in file_paths or "docker-compose.yaml" in file_paths or "Dockerfile" in file_paths:
            self._add(evidence, "docker", "container manifests")
        if any(path.startswith("deployment/") for path in file_paths):
            self._add(evidence, "deployment-architecture", "deployment directory")
        if "frontend/app/page.tsx" in file_paths or any(path.startswith("frontend/app/") for path in file_paths):
            self._add(evidence, "nextjs", "frontend app router directory")
        if any(path.startswith("core/graph/") for path in file_paths):
            self._add(evidence, "langgraph", "core graph package")
        if any(path.startswith("core/agents/qa/") for path in file_paths):
            self._add(evidence, "qa-automation", "qa agent package")

    async def _detect_python(
        self,
        root_path: Path,
        files: tuple[RepositoryFileIndex, ...],
        evidence: dict[str, set[str]],
    ) -> None:
        python_manifests = [file for file in files if file.path in {"requirements.txt", "pyproject.toml"}]
        python_sources = [file for file in files if file.language == "python"]
        for file in python_manifests + python_sources[:200]:
            text = self._read_text(root_path / file.path)
            lowered = text.lower()
            if "fastapi" in lowered:
                self._add(evidence, "fastapi", file.path)
            if "pydantic" in lowered:
                self._add(evidence, "pydantic", file.path)
            if "langgraph" in lowered:
                self._add(evidence, "langgraph", file.path)
            if "pytest" in lowered:
                self._add(evidence, "pytest", file.path)
            if "playwright" in lowered:
                self._add(evidence, "playwright", file.path)
            if "selenium" in lowered:
                self._add(evidence, "selenium", file.path)

    async def _detect_node(
        self,
        root_path: Path,
        files: tuple[RepositoryFileIndex, ...],
        evidence: dict[str, set[str]],
    ) -> None:
        package_files = [file for file in files if file.path.endswith("package.json")]
        for file in package_files:
            payload = self._read_json(root_path / file.path)
            dependencies = {
                **payload.get("dependencies", {}),
                **payload.get("devDependencies", {}),
            }
            for package_name in dependencies:
                lowered = package_name.lower()
                if lowered == "next":
                    self._add(evidence, "nextjs", file.path)
                elif lowered == "react":
                    self._add(evidence, "react", file.path)
                elif lowered == "tailwindcss":
                    self._add(evidence, "tailwindcss", file.path)
                elif lowered.startswith("@radix-ui/") or lowered == "class-variance-authority":
                    self._add(evidence, "shadcn-ui", file.path)
                elif lowered == "@playwright/test":
                    self._add(evidence, "playwright", file.path)

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _read_json(self, path: Path) -> dict[str, object]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _add(self, evidence: dict[str, set[str]], name: str, source: str) -> None:
        evidence.setdefault(name, set()).add(source)

    def _category(self, name: str) -> str:
        categories = {
            "fastapi": "backend",
            "pydantic": "contracts",
            "langgraph": "orchestration",
            "pytest": "testing",
            "playwright": "testing",
            "selenium": "testing",
            "nextjs": "frontend",
            "react": "frontend",
            "tailwindcss": "frontend",
            "shadcn-ui": "frontend",
            "docker": "deployment",
            "deployment-architecture": "deployment",
            "qa-automation": "quality",
        }
        return categories.get(name, "tooling")

    def _confidence(self, name: str, evidence: set[str]) -> float:
        if name in {"fastapi", "nextjs", "langgraph", "docker"} and len(evidence) >= 2:
            return 0.95
        if evidence:
            return 0.8
        return 0.0
