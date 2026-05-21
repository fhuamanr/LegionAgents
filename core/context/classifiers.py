"""Context source classification utilities."""

from pathlib import Path

from core.contracts.context import (
    ContextDocumentKind,
    ContextPriority,
    ContextSectionName,
)


class ContextSourceClassifier:
    """Classifies source files into document kind, section, and priority."""

    def classify_kind(self, path: Path) -> ContextDocumentKind:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return ContextDocumentKind.MARKDOWN
        if suffix == ".mmd":
            return ContextDocumentKind.MERMAID
        if suffix == ".txt":
            return ContextDocumentKind.TEXT
        return ContextDocumentKind.UNKNOWN

    def classify_section(self, path: Path) -> ContextSectionName:
        name = path.stem.lower().replace("_", "-")
        if name == "gravity":
            return ContextSectionName.GRAVITY_RULES
        if name in {"anti-gravity", "anti-gravity-rules"}:
            return ContextSectionName.ANTI_GRAVITY_RULES
        if name == "personality":
            return ContextSectionName.PERSONALITY
        if name in {"architecture", "constraints", "architecture-constraints"}:
            return ContextSectionName.ARCHITECTURE_CONSTRAINTS
        if "standard" in name or name in {"naming", "security", "testing", "forbidden"}:
            return ContextSectionName.STANDARDS
        if "prompt" in name:
            return ContextSectionName.PROMPTS
        if name.startswith("diagram") or path.suffix.lower() == ".mmd":
            return ContextSectionName.DIAGRAMS
        return ContextSectionName.GENERAL

    def classify_priority(self, section: ContextSectionName) -> ContextPriority:
        if section in {
            ContextSectionName.GRAVITY_RULES,
            ContextSectionName.ANTI_GRAVITY_RULES,
            ContextSectionName.ARCHITECTURE_CONSTRAINTS,
        }:
            return ContextPriority.CRITICAL
        if section in {ContextSectionName.PERSONALITY, ContextSectionName.STANDARDS}:
            return ContextPriority.HIGH
        if section == ContextSectionName.PROMPTS:
            return ContextPriority.NORMAL
        return ContextPriority.LOW

