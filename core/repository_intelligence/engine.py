"""Repository Intelligence Engine orchestration."""

import logging

from core.contracts.repository_intelligence import RepositoryIntelligenceReport, RepositoryScanRequest
from core.repository_intelligence.architecture import ArchitectureDetector
from core.repository_intelligence.dependencies import DependencyAnalyzer
from core.repository_intelligence.frameworks import FrameworkDetector
from core.repository_intelligence.graph import RepositoryGraphGenerator
from core.repository_intelligence.scanners import RepositoryScanner, scanner_for, summarize_languages
from core.repository_intelligence.summarizer import RepositoryArchitectureSummarizer

logger = logging.getLogger(__name__)


class RepositoryIntelligenceEngine:
    """Coordinates read-only repository scanning, detection, graphing, and summarization."""

    def __init__(
        self,
        scanner: RepositoryScanner | None = None,
        framework_detector: FrameworkDetector | None = None,
        dependency_analyzer: DependencyAnalyzer | None = None,
        architecture_detector: ArchitectureDetector | None = None,
        graph_generator: RepositoryGraphGenerator | None = None,
        summarizer: RepositoryArchitectureSummarizer | None = None,
    ) -> None:
        self._scanner = scanner
        self._framework_detector = framework_detector or FrameworkDetector()
        self._dependency_analyzer = dependency_analyzer or DependencyAnalyzer()
        self._architecture_detector = architecture_detector or ArchitectureDetector()
        self._graph_generator = graph_generator or RepositoryGraphGenerator()
        self._summarizer = summarizer or RepositoryArchitectureSummarizer()

    async def analyze(self, request: RepositoryScanRequest) -> RepositoryIntelligenceReport:
        """Analyze a repository and return a structured intelligence report."""

        scanner = self._scanner or scanner_for(request.ingestion_kind)
        logger.info("repository_intelligence.scan_started", extra={"ingestion_kind": request.ingestion_kind})
        root_path, files = await scanner.scan(request)
        languages = summarize_languages(files)
        frameworks = await self._framework_detector.detect(root_path, files)
        nodes, edges = await self._dependency_analyzer.analyze(root_path, files)
        architecture = await self._architecture_detector.detect(files, frameworks)
        graph = await self._graph_generator.generate(nodes, edges)
        summary = await self._summarizer.summarize(languages, frameworks, architecture, graph)
        logger.info(
            "repository_intelligence.scan_completed",
            extra={"file_count": len(files), "framework_count": len(frameworks), "edge_count": len(graph.edges)},
        )
        return RepositoryIntelligenceReport(
            request=request,
            root_path=root_path,
            files=files,
            languages=languages,
            frameworks=frameworks,
            architecture=architecture,
            graph=graph,
            summary=summary,
            metadata={
                "file_count": len(files),
                "language_count": len(languages),
                "framework_count": len(frameworks),
                "architecture_detection_count": len(architecture),
            },
        )
