"""Repository intelligence engine."""

from core.repository_intelligence.architecture import ArchitectureDetector
from core.repository_intelligence.dependencies import DependencyAnalyzer
from core.repository_intelligence.engine import RepositoryIntelligenceEngine
from core.repository_intelligence.frameworks import FrameworkDetector
from core.repository_intelligence.graph import RepositoryGraphGenerator
from core.repository_intelligence.scanners import (
    GitHubRepositoryScanner,
    LocalRepositoryScanner,
    MountedRepositoryScanner,
    RepositoryScanner,
    scanner_for,
    summarize_languages,
)
from core.repository_intelligence.summarizer import RepositoryArchitectureSummarizer

__all__ = [
    "ArchitectureDetector",
    "DependencyAnalyzer",
    "FrameworkDetector",
    "GitHubRepositoryScanner",
    "LocalRepositoryScanner",
    "MountedRepositoryScanner",
    "RepositoryArchitectureSummarizer",
    "RepositoryGraphGenerator",
    "RepositoryIntelligenceEngine",
    "RepositoryScanner",
    "scanner_for",
    "summarize_languages",
]
