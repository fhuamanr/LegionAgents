"""Context engineering engine."""

from pathlib import Path

from core.context import FileSystemAgentContextLoader
from core.context.assemblers import ContextPackageAssembler
from core.context_engineering.budgeting import TokenBudgetManager
from core.context_engineering.compression import ContextCompressor, ExtractiveContextCompressor
from core.context_engineering.memory import MemoryContextProvider
from core.context_engineering.models import (
    ContextEngineeringRequest,
    ContextEngineeringResult,
    ContextItem,
    ContextItemSource,
)
from core.context_engineering.repository import RepositorySummaryProvider
from core.context_engineering.selection import ContextSelector, SmartContextSelector
from core.context_engineering.summarization import ArchitectureSummarizer
from core.contracts.context import ContextDocument, ContextLoadRequest, ContextPriority, ContextSectionName


class ContextEngineeringEngine:
    """Builds compact, isolated, agent-specific context packages."""

    def __init__(
        self,
        context_loader: FileSystemAgentContextLoader | None = None,
        repository_provider: RepositorySummaryProvider | None = None,
        architecture_summarizer: ArchitectureSummarizer | None = None,
        memory_provider: MemoryContextProvider | None = None,
        selector: ContextSelector | None = None,
        compressor: ContextCompressor | None = None,
        budget_manager: TokenBudgetManager | None = None,
        assembler: ContextPackageAssembler | None = None,
    ) -> None:
        self._context_loader = context_loader or FileSystemAgentContextLoader()
        self._repository_provider = repository_provider or RepositorySummaryProvider()
        self._architecture_summarizer = architecture_summarizer or ArchitectureSummarizer()
        self._memory_provider = memory_provider or MemoryContextProvider()
        self._selector = selector or SmartContextSelector()
        self._compressor = compressor or ExtractiveContextCompressor()
        self._budget_manager = budget_manager or TokenBudgetManager()
        self._assembler = assembler or ContextPackageAssembler()

    async def build(self, request: ContextEngineeringRequest) -> ContextEngineeringResult:
        warnings: list[str] = []
        raw_context_result = await self._context_loader.load_request(
            ContextLoadRequest(
                agent_name=request.agent_name,
                root_path=request.agent_context_path,
                include_sections=request.include_sections,
                exclude_sections=request.exclude_sections,
            )
        )
        warnings.extend(raw_context_result.warnings)

        candidates = list(self._items_from_agent_context(request, raw_context_result.context))
        candidates.extend(await self._repository_items(request))
        candidates.extend(await self._architecture_items(request))
        candidates.extend(self._upstream_items(request))
        candidates.extend(await self._memory_provider.provide(request))

        selected_candidates = await self._selector.select(tuple(candidates))
        compressed = await self._compressor.compress(selected_candidates, request.config)
        selected, dropped = self._budget_manager.fit(compressed, request.config)
        final_context = await self._assembler.assemble(
            agent_name=request.agent_name,
            documents=tuple(self._documents_from_items(selected)),
        )
        token_hint = sum(item.token_hint for item in selected)
        return ContextEngineeringResult(
            agent_name=request.agent_name,
            context=final_context.model_copy(
                update={
                    "metadata": {
                        **final_context.metadata,
                        "engineered": True,
                        "selected_item_count": len(selected),
                        "dropped_item_count": len(dropped),
                    }
                }
            ),
            selected_items=selected,
            dropped_items=dropped,
            warnings=tuple(warnings),
            token_hint=token_hint,
            metadata={
                "candidate_count": len(candidates),
                "selected_count": len(selected),
                "dropped_count": len(dropped),
                "token_budget": request.config.context_token_budget,
            },
        )

    def _items_from_agent_context(
        self,
        request: ContextEngineeringRequest,
        agent_context: object,
    ) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        for section in getattr(agent_context, "sections", tuple()):
            for document in section.documents:
                items.append(
                    ContextItem(
                        id=f"agent-rules-{document.path}",
                        source=ContextItemSource.AGENT_RULES,
                        title=document.name,
                        content=document.content,
                        priority=document.priority,
                        token_hint=document.token_hint,
                        metadata={
                            **document.metadata,
                            "path": str(document.path),
                            "agent_name": request.agent_name,
                            "requested_agent": request.agent_name,
                            "section": document.section.value,
                        },
                    )
                )
        return tuple(items)

    async def _repository_items(
        self,
        request: ContextEngineeringRequest,
    ) -> tuple[ContextItem, ...]:
        if not request.config.enable_repository_summary:
            return tuple()
        return await self._repository_provider.provide(request.repository_path)

    async def _architecture_items(
        self,
        request: ContextEngineeringRequest,
    ) -> tuple[ContextItem, ...]:
        if not request.config.enable_architecture_summary:
            return tuple()
        summary = await self._architecture_summarizer.summarize(request.architecture_context)
        if not summary:
            return tuple()
        return (
            ContextItem(
                id="architecture-summary",
                source=ContextItemSource.ARCHITECTURE_SUMMARY,
                title="Architecture Summary",
                content=summary,
                priority=ContextPriority.HIGH,
                token_hint=max(1, len(summary) // 4),
            ),
        )

    def _upstream_items(self, request: ContextEngineeringRequest) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        for index, content in enumerate(request.upstream_context):
            if not content.strip():
                continue
            items.append(
                ContextItem(
                    id=f"upstream-{index}",
                    source=ContextItemSource.UPSTREAM,
                    title=f"Upstream Context {index + 1}",
                    content=content,
                    priority=ContextPriority.HIGH,
                    token_hint=max(1, len(content) // 4),
                )
            )
        return tuple(items)

    def _documents_from_items(self, items: tuple[ContextItem, ...]) -> tuple[ContextDocument, ...]:
        documents: list[ContextDocument] = []
        for item in items:
            section = self._section_for_item(item)
            documents.append(
                ContextDocument(
                    name=item.title,
                    path=Path(f"engineered/{item.id}.md"),
                    content=item.content,
                    section=section,
                    priority=item.priority,
                    token_hint=item.token_hint,
                    metadata=item.metadata,
                )
            )
        return tuple(documents)

    def _section_for_item(self, item: ContextItem) -> ContextSectionName:
        if item.source == ContextItemSource.ARCHITECTURE_SUMMARY:
            return ContextSectionName.ARCHITECTURE_CONSTRAINTS
        if item.source == ContextItemSource.AGENT_RULES:
            section = item.metadata.get("section")
            if isinstance(section, str):
                try:
                    return ContextSectionName(section)
                except ValueError:
                    return ContextSectionName.GENERAL
        return ContextSectionName.GENERAL

