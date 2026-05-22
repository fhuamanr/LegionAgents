"""Repository architecture summarization."""

from core.contracts.repository_intelligence import (
    ArchitectureDetection,
    FrameworkDetection,
    RepositoryGraph,
    RepositoryIntelligenceSummary,
    RepositoryLanguageSummary,
)


class RepositoryArchitectureSummarizer:
    """Produces compact summaries for agents and dashboards."""

    async def summarize(
        self,
        languages: tuple[RepositoryLanguageSummary, ...],
        frameworks: tuple[FrameworkDetection, ...],
        architecture: tuple[ArchitectureDetection, ...],
        graph: RepositoryGraph,
    ) -> RepositoryIntelligenceSummary:
        """Summarize repository intelligence outputs."""

        primary_languages = tuple(language.language for language in sorted(languages, key=lambda item: item.file_count, reverse=True)[:5])
        primary_frameworks = tuple(framework.name for framework in sorted(frameworks, key=lambda item: item.confidence, reverse=True)[:8])
        detected_patterns = tuple(detection.pattern for detection in architecture)
        key_modules = tuple(node.path for node in graph.nodes if node.kind in {"config", "file"} and node.path.count("/") <= 1)[:12]
        framework_text = ", ".join(primary_frameworks) or "no framework evidence"
        language_text = ", ".join(primary_languages) or "unknown languages"
        pattern_text = ", ".join(pattern.value for pattern in detected_patterns)
        risks = self._risks(graph, frameworks)

        return RepositoryIntelligenceSummary(
            title="Repository Intelligence Summary",
            overview=(
                f"Repository uses {language_text}; detected {framework_text}; "
                f"architecture signals: {pattern_text}."
            ),
            primary_languages=primary_languages,
            primary_frameworks=primary_frameworks,
            detected_patterns=detected_patterns,
            key_modules=key_modules,
            risks=risks,
        )

    def _risks(self, graph: RepositoryGraph, frameworks: tuple[FrameworkDetection, ...]) -> tuple[str, ...]:
        risks: list[str] = []
        if graph.metadata.get("external_dependency_count", 0) > 50:
            risks.append("High number of external dependencies detected; dependency governance should be enforced.")
        framework_names = {framework.name for framework in frameworks}
        if "pytest" not in framework_names and "playwright" not in framework_names:
            risks.append("No explicit automated testing framework detected.")
        return tuple(risks)
