"""Repository and architecture summarization."""

from pathlib import Path

from core.agents.developer.repository import FileSystemRepositoryAnalyzer, RepositoryAnalysis


class RepositorySummarizer:
    """Builds compact repository summaries."""

    def __init__(self, analyzer: FileSystemRepositoryAnalyzer | None = None) -> None:
        self._analyzer = analyzer or FileSystemRepositoryAnalyzer()

    async def summarize(self, repository_path: Path) -> str:
        analysis = await self._analyzer.analyze(repository_path)
        return self._render(analysis)

    def _render(self, analysis: RepositoryAnalysis) -> str:
        languages = ", ".join(analysis.detected_languages) or "unknown"
        directories = "\n".join(f"- {item}" for item in analysis.directories[:40]) or "None detected"
        tests = "\n".join(f"- {item}" for item in analysis.test_paths[:30]) or "None detected"
        files = "\n".join(f"- {item.path}" for item in analysis.files[:60]) or "None detected"
        return (
            f"Repository root: {analysis.root_path}\n"
            f"Detected languages: {languages}\n\n"
            f"Directories:\n{directories}\n\n"
            f"Representative files:\n{files}\n\n"
            f"Test paths:\n{tests}"
        )


class ArchitectureSummarizer:
    """Builds compact architecture summaries."""

    async def summarize(self, architecture_context: str | None) -> str:
        if not architecture_context or not architecture_context.strip():
            return ""
        lines = [line.strip() for line in architecture_context.splitlines() if line.strip()]
        selected = lines[:40]
        return "\n".join(selected)

