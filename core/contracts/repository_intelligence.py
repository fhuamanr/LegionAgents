"""Contracts for repository intelligence and architecture analysis."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata
from core.contracts.repository import RepositoryProvider


class RepositoryIngestionKind(StrEnum):
    """Supported repository intelligence ingestion boundaries."""

    LOCAL = "local"
    MOUNTED = "mounted"
    GITHUB = "github"


class RepositoryArchitecturePattern(StrEnum):
    """Architecture patterns the intelligence engine can detect."""

    CLEAN_ARCHITECTURE = "clean_architecture"
    LAYERED_ARCHITECTURE = "layered_architecture"
    HEXAGONAL_ARCHITECTURE = "hexagonal_architecture"
    MULTI_AGENT_PLATFORM = "multi_agent_platform"
    FASTAPI_BACKEND = "fastapi_backend"
    NEXTJS_APP_ROUTER = "nextjs_app_router"
    DOCKERIZED_PLATFORM = "dockerized_platform"
    QA_AUTOMATION_SANDBOX = "qa_automation_sandbox"
    UNKNOWN = "unknown"


class DependencyRelationshipKind(StrEnum):
    """Kinds of relationships between repository modules."""

    IMPORTS = "imports"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    CONFIGURES = "configures"
    TESTS = "tests"


class RepositoryScanRequest(ContractBaseModel):
    """Request to analyze a repository without mutating it."""

    root_path: Path | None = None
    repository_url: str | None = None
    ingestion_kind: RepositoryIngestionKind = RepositoryIngestionKind.LOCAL
    provider: RepositoryProvider = RepositoryProvider.UNKNOWN
    max_files: int = Field(default=2_000, ge=1)
    max_file_size_bytes: int = Field(default=512_000, ge=1)
    include_hidden: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryFileIndex(ContractBaseModel):
    """Scanned repository file metadata."""

    path: str
    size_bytes: int = Field(ge=0)
    suffix: str = ""
    language: str | None = None
    is_test: bool = False
    is_config: bool = False
    is_documentation: bool = False


class RepositoryLanguageSummary(ContractBaseModel):
    """Per-language repository footprint."""

    language: str
    file_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)


class FrameworkDetection(ContractBaseModel):
    """Detected framework, tool, or platform capability."""

    name: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = Field(default_factory=tuple)


class ArchitectureDetection(ContractBaseModel):
    """Detected repository architecture pattern."""

    pattern: RepositoryArchitecturePattern
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = Field(default_factory=tuple)


class ModuleNode(ContractBaseModel):
    """Repository graph node for a module, package, file, or manifest."""

    id: str
    label: str
    path: str
    language: str | None = None
    kind: str = "file"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModuleDependency(ContractBaseModel):
    """Directed dependency relationship between repository modules."""

    source: str
    target: str
    kind: DependencyRelationshipKind = DependencyRelationshipKind.IMPORTS
    import_name: str | None = None
    evidence: str | None = None


class RepositoryGraph(ContractBaseModel):
    """Repository module graph suitable for visualization and retrieval."""

    nodes: tuple[ModuleNode, ...] = Field(default_factory=tuple)
    edges: tuple[ModuleDependency, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryIntelligenceSummary(ContractBaseModel):
    """Human and agent readable repository summary."""

    title: str
    overview: str
    primary_languages: tuple[str, ...] = Field(default_factory=tuple)
    primary_frameworks: tuple[str, ...] = Field(default_factory=tuple)
    detected_patterns: tuple[RepositoryArchitecturePattern, ...] = Field(default_factory=tuple)
    key_modules: tuple[str, ...] = Field(default_factory=tuple)
    risks: tuple[str, ...] = Field(default_factory=tuple)


class RepositoryIntelligenceReport(ContractBaseModel):
    """Complete repository intelligence output contract."""

    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    request: RepositoryScanRequest
    root_path: Path
    files: tuple[RepositoryFileIndex, ...] = Field(default_factory=tuple)
    languages: tuple[RepositoryLanguageSummary, ...] = Field(default_factory=tuple)
    frameworks: tuple[FrameworkDetection, ...] = Field(default_factory=tuple)
    architecture: tuple[ArchitectureDetection, ...] = Field(default_factory=tuple)
    graph: RepositoryGraph = Field(default_factory=RepositoryGraph)
    summary: RepositoryIntelligenceSummary
    metadata: dict[str, Any] = Field(default_factory=dict)
