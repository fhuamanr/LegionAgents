"""Context contracts used to isolate agent knowledge."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata


class ContextDocumentKind(StrEnum):
    """Supported context source document types."""

    MARKDOWN = "markdown"
    MERMAID = "mermaid"
    TEXT = "text"
    UNKNOWN = "unknown"


class ContextSectionName(StrEnum):
    """Canonical context sections used by prompt composition."""

    GRAVITY_RULES = "gravity_rules"
    ANTI_GRAVITY_RULES = "anti_gravity_rules"
    PERSONALITY = "personality"
    ARCHITECTURE_CONSTRAINTS = "architecture_constraints"
    STANDARDS = "standards"
    PROMPTS = "prompts"
    DIAGRAMS = "diagrams"
    GENERAL = "general"


class ContextPriority(StrEnum):
    """Priority hints used when trimming context packages."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ContextSource(ContractBaseModel):
    """Reference to a source file before content is loaded."""

    path: Path
    kind: ContextDocumentKind = ContextDocumentKind.UNKNOWN
    section: ContextSectionName = ContextSectionName.GENERAL
    priority: ContextPriority = ContextPriority.NORMAL


class ContextDocument(ContractBaseModel):
    """A single source document loaded for an agent."""

    name: str = Field(min_length=1)
    path: Path
    content: str
    kind: ContextDocumentKind = ContextDocumentKind.UNKNOWN
    section: ContextSectionName = ContextSectionName.GENERAL
    priority: ContextPriority = ContextPriority.NORMAL
    token_hint: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextSection(ContractBaseModel):
    """Named group of context documents."""

    name: ContextSectionName
    documents: tuple[ContextDocument, ...] = Field(default_factory=tuple)
    priority: ContextPriority = ContextPriority.NORMAL


class AgentContext(ContractBaseModel):
    """Isolated context loaded for one agent only."""

    agent_name: str = Field(min_length=1)
    sections: tuple[ContextSection, ...] = Field(default_factory=tuple)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def render(self) -> str:
        """Render context deterministically for prompt composition."""

        rendered_sections: list[str] = []
        for section in self.sections:
            rendered_documents = [
                f"## {document.name}\n\n{document.content.strip()}"
                for document in section.documents
                if document.content.strip()
            ]
            if rendered_documents:
                rendered_sections.append(
                    f"# {section.name.value}\n\n" + "\n\n".join(rendered_documents)
                )
        return "\n\n".join(rendered_sections)


class ContextLoadRequest(ContractBaseModel):
    """Request to load context for a single agent."""

    agent_name: str = Field(min_length=1)
    root_path: Path
    include_sections: tuple[ContextSectionName, ...] | None = None
    exclude_sections: tuple[ContextSectionName, ...] = Field(default_factory=tuple)
    max_token_hint: int | None = Field(default=None, ge=1)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)


class ContextLoadResult(ContractBaseModel):
    """Result returned by a context loading strategy."""

    request: ContextLoadRequest
    context: AgentContext
    sources: tuple[ContextSource, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
