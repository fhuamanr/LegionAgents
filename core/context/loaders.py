"""Context loading strategies."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.context.assemblers import ContextPackageAssembler
from core.context.classifiers import ContextSourceClassifier
from core.context.readers import ContextDocumentReader, FileSystemContextDocumentReader
from core.contracts.agents import AgentDefinition
from core.contracts.context import (
    AgentContext,
    ContextDocument,
    ContextLoadRequest,
    ContextLoadResult,
    ContextSectionName,
    ContextSource,
)


class AgentContextLoader(ABC):
    """Loads isolated context for an agent."""

    @abstractmethod
    async def load(self, agent: AgentDefinition) -> AgentContext:
        """Load context for a single agent."""

    @abstractmethod
    async def load_request(self, request: ContextLoadRequest) -> ContextLoadResult:
        """Load context using an explicit request contract."""


class ContextSourceDiscoverer(ABC):
    """Discovers raw context source files."""

    @abstractmethod
    async def discover(self, root_path: Path) -> tuple[ContextSource, ...]:
        """Discover context sources under a root path."""


class FileSystemContextSourceDiscoverer(ContextSourceDiscoverer):
    """Discovers context source files from a filesystem tree."""

    def __init__(
        self,
        classifier: ContextSourceClassifier | None = None,
        allowed_suffixes: set[str] | None = None,
    ) -> None:
        self._classifier = classifier or ContextSourceClassifier()
        self._allowed_suffixes = allowed_suffixes or {".md", ".mmd", ".txt"}

    async def discover(self, root_path: Path) -> tuple[ContextSource, ...]:
        if not root_path.exists():
            return tuple()

        sources: list[ContextSource] = []
        for path in sorted(root_path.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self._allowed_suffixes:
                continue
            section = self._classifier.classify_section(path)
            sources.append(
                ContextSource(
                    path=path,
                    kind=self._classifier.classify_kind(path),
                    section=section,
                    priority=self._classifier.classify_priority(section),
                )
            )
        return tuple(sources)


class FileSystemAgentContextLoader(AgentContextLoader):
    """Loads and assembles isolated context from an agent directory."""

    def __init__(
        self,
        discoverer: ContextSourceDiscoverer | None = None,
        reader: ContextDocumentReader | None = None,
        assembler: ContextPackageAssembler | None = None,
        allowed_suffixes: set[str] | None = None,
    ) -> None:
        self._discoverer = discoverer or FileSystemContextSourceDiscoverer(
            allowed_suffixes=allowed_suffixes,
        )
        self._reader = reader or FileSystemContextDocumentReader()
        self._assembler = assembler or ContextPackageAssembler()

    async def load(self, agent: AgentDefinition) -> AgentContext:
        result = await self.load_request(
            ContextLoadRequest(
                agent_name=agent.name,
                root_path=agent.context_path,
            )
        )
        return result.context

    async def load_request(self, request: ContextLoadRequest) -> ContextLoadResult:
        warnings: list[str] = []
        if not request.root_path.exists():
            empty_context = AgentContext(
                agent_name=request.agent_name,
                metadata={"document_count": 0},
            )
            return ContextLoadResult(
                request=request,
                context=empty_context,
                warnings=(f"Context path does not exist: {request.root_path}",),
            )

        sources = await self._discoverer.discover(request.root_path)
        filtered_sources = self._filter_sources(
            sources=sources,
            include_sections=request.include_sections,
            exclude_sections=request.exclude_sections,
        )

        documents: list[ContextDocument] = []
        for source in filtered_sources:
            try:
                content = await self._reader.read_text(source.path)
            except UnicodeDecodeError as exc:
                warnings.append(f"Unable to decode context file {source.path}: {exc}")
                continue

            if not content.strip():
                warnings.append(f"Empty context file skipped: {source.path}")
                continue

            documents.append(
                ContextDocument(
                    name=self._display_name(source.path),
                    path=source.path,
                    content=content,
                    kind=source.kind,
                    section=source.section,
                    priority=source.priority,
                    token_hint=max(1, len(content) // 4),
                    metadata={"relative_path": str(source.path.relative_to(request.root_path))},
                )
            )

        context = await self._assembler.assemble(
            agent_name=request.agent_name,
            documents=tuple(documents),
            max_token_hint=request.max_token_hint,
        )
        return ContextLoadResult(
            request=request,
            context=context,
            sources=filtered_sources,
            warnings=tuple(warnings),
        )

    def _filter_sources(
        self,
        sources: tuple[ContextSource, ...],
        include_sections: tuple[ContextSectionName, ...] | None,
        exclude_sections: tuple[ContextSectionName, ...],
    ) -> tuple[ContextSource, ...]:
        included = [
            source
            for source in sources
            if include_sections is None or source.section in include_sections
        ]
        return tuple(source for source in included if source.section not in exclude_sections)

    def _display_name(self, path: Path) -> str:
        return path.stem.replace("-", " ").replace("_", " ").title()
