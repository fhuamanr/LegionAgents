"""Architecture pattern detection for repository intelligence."""

from core.contracts.repository_intelligence import (
    ArchitectureDetection,
    FrameworkDetection,
    RepositoryArchitecturePattern,
    RepositoryFileIndex,
)


class ArchitectureDetector:
    """Detects architecture patterns from repository shape and framework evidence."""

    async def detect(
        self,
        files: tuple[RepositoryFileIndex, ...],
        frameworks: tuple[FrameworkDetection, ...],
    ) -> tuple[ArchitectureDetection, ...]:
        """Detect architecture patterns."""

        paths = {file.path for file in files}
        dirs = self._directories(paths)
        framework_names = {framework.name for framework in frameworks}
        detections: list[ArchitectureDetection] = []

        if {"core", "app"}.issubset(dirs) and {"contracts", "runtime"}.intersection(dirs):
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.CLEAN_ARCHITECTURE,
                    confidence=0.86,
                    evidence=tuple(sorted({"core/", "app/", "contracts/runtime packages"})),
                )
            )
        if {"routers", "services", "dependencies"}.intersection(dirs) and "fastapi" in framework_names:
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.FASTAPI_BACKEND,
                    confidence=0.9,
                    evidence=tuple(sorted({"FastAPI framework", "router/service directories"})),
                )
            )
        if any(path.startswith("frontend/app/") for path in paths) and "nextjs" in framework_names:
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.NEXTJS_APP_ROUTER,
                    confidence=0.92,
                    evidence=("frontend/app/", "Next.js framework"),
                )
            )
        if {"ba", "architect", "developer", "qa", "docs"}.intersection(dirs) and any(
            path.startswith("core/agents/") for path in paths
        ):
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.MULTI_AGENT_PLATFORM,
                    confidence=0.88,
                    evidence=("specialized agent directories", "core/agents package"),
                )
            )
        if "docker" in framework_names:
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.DOCKERIZED_PLATFORM,
                    confidence=0.9,
                    evidence=("Docker manifests",),
                )
            )
        if "playwright" in framework_names or "selenium" in framework_names:
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.QA_AUTOMATION_SANDBOX,
                    confidence=0.78,
                    evidence=("browser automation dependencies",),
                )
            )
        if not detections:
            detections.append(
                ArchitectureDetection(
                    pattern=RepositoryArchitecturePattern.UNKNOWN,
                    confidence=0.1,
                    evidence=("No known repository pattern matched",),
                )
            )
        return tuple(detections)

    def _directories(self, paths: set[str]) -> set[str]:
        directories: set[str] = set()
        for path in paths:
            parts = path.split("/")
            directories.update(parts[:-1])
        return directories
