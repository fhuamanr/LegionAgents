"""Context package assembly."""

from collections import defaultdict

from core.contracts.context import (
    AgentContext,
    ContextDocument,
    ContextPriority,
    ContextSection,
    ContextSectionName,
)


class ContextPackageAssembler:
    """Builds an isolated agent context from loaded documents."""

    _section_order = (
        ContextSectionName.GRAVITY_RULES,
        ContextSectionName.ANTI_GRAVITY_RULES,
        ContextSectionName.PERSONALITY,
        ContextSectionName.ARCHITECTURE_CONSTRAINTS,
        ContextSectionName.STANDARDS,
        ContextSectionName.PROMPTS,
        ContextSectionName.DIAGRAMS,
        ContextSectionName.GENERAL,
    )

    async def assemble(
        self,
        agent_name: str,
        documents: tuple[ContextDocument, ...],
        max_token_hint: int | None = None,
    ) -> AgentContext:
        selected = self._apply_token_budget(documents, max_token_hint)
        grouped: dict[ContextSectionName, list[ContextDocument]] = defaultdict(list)
        for document in selected:
            grouped[document.section].append(document)

        sections = [
            ContextSection(
                name=section_name,
                documents=tuple(sorted(grouped[section_name], key=lambda item: str(item.path))),
                priority=self._section_priority(grouped[section_name]),
            )
            for section_name in self._section_order
            if grouped.get(section_name)
        ]
        return AgentContext(
            agent_name=agent_name,
            sections=tuple(sections),
            metadata={"document_count": len(selected)},
        )

    def _apply_token_budget(
        self,
        documents: tuple[ContextDocument, ...],
        max_token_hint: int | None,
    ) -> tuple[ContextDocument, ...]:
        if max_token_hint is None:
            return documents

        selected: list[ContextDocument] = []
        total = 0
        for document in sorted(documents, key=lambda item: self._priority_rank(item.priority)):
            if total + document.token_hint > max_token_hint:
                continue
            selected.append(document)
            total += document.token_hint
        return tuple(selected)

    def _priority_rank(self, priority: ContextPriority) -> int:
        return {
            ContextPriority.CRITICAL: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.NORMAL: 2,
            ContextPriority.LOW: 3,
        }[priority]

    def _section_priority(self, documents: list[ContextDocument]) -> ContextPriority:
        if not documents:
            return ContextPriority.NORMAL
        return min(documents, key=lambda item: self._priority_rank(item.priority)).priority
