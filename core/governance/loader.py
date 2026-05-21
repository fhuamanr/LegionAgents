"""Governance policy loaders."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.governance.models import (
    GovernancePolicy,
    GovernanceRule,
    RuleCategory,
    RuleEffect,
    RulePriority,
    RuleSource,
)


class PolicyLoader(ABC):
    """Policy loading boundary."""

    @abstractmethod
    async def load(self, root_path: Path, scope: str, source: RuleSource) -> GovernancePolicy:
        """Load a policy from a path."""


class MarkdownPolicyLoader(PolicyLoader):
    """Loads markdown bullet rules from a directory or file."""

    _category_by_name = {
        "security": RuleCategory.SECURITY,
        "coding-standards": RuleCategory.CODING_STANDARDS,
        "coding-guidelines": RuleCategory.CODING_STANDARDS,
        "clean-architecture": RuleCategory.ARCHITECTURE,
        "architecture": RuleCategory.ARCHITECTURE,
        "test-strategy": RuleCategory.QA,
        "severity-rules": RuleCategory.QA,
        "documentation": RuleCategory.DOCUMENTATION,
        "docs": RuleCategory.DOCUMENTATION,
    }

    async def load(self, root_path: Path, scope: str, source: RuleSource) -> GovernancePolicy:
        paths = self._paths(root_path)
        rules: list[GovernanceRule] = []
        for path in paths:
            rules.extend(self._rules_from_markdown(path, scope, source))
        return GovernancePolicy(
            name=f"{scope} Markdown Governance Policy",
            scope=scope,
            rules=tuple(rules),
            metadata={"source_path": str(root_path)},
        )

    def _paths(self, root_path: Path) -> tuple[Path, ...]:
        if root_path.is_file() and root_path.suffix.lower() == ".md":
            return (root_path,)
        if not root_path.exists():
            return tuple()
        return tuple(sorted(path for path in root_path.rglob("*.md") if path.is_file()))

    def _rules_from_markdown(
        self,
        path: Path,
        scope: str,
        source: RuleSource,
    ) -> tuple[GovernanceRule, ...]:
        content = path.read_text(encoding="utf-8")
        rules: list[GovernanceRule] = []
        for index, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            description = stripped[2:].strip()
            if not description:
                continue
            rules.append(
                GovernanceRule(
                    id=f"{scope}.{path.stem}.{index}",
                    description=description,
                    effect=self._effect(path, description),
                    category=self._category(path, scope),
                    priority=self._priority(path, description),
                    source=source,
                    allow_local_override=False,
                    source_path=path,
                    metadata={"line": index},
                )
            )
        return tuple(rules)

    def _effect(self, path: Path, description: str) -> RuleEffect:
        text = f"{path.stem} {description}".lower()
        if any(term in text for term in ("forbid", "forbidden", "anti-gravity", "nunca", "no ")):
            return RuleEffect.FORBID
        if any(term in text for term in ("siempre", "must", "required", "require")):
            return RuleEffect.REQUIRE
        return RuleEffect.RECOMMEND

    def _category(self, path: Path, scope: str) -> RuleCategory:
        if scope == "qa" and path.stem.lower() in {"gravity", "anti-gravity"}:
            return RuleCategory.QA
        if scope == "developer" and path.stem.lower() in {
            "gravity",
            "anti-gravity",
            "forbidden",
            "coding-standards",
            "testing",
            "security",
            "architecture",
        }:
            if path.stem.lower() == "security":
                return RuleCategory.SECURITY
            if path.stem.lower() in {"architecture"}:
                return RuleCategory.ARCHITECTURE
            return RuleCategory.CODING_STANDARDS
        return self._category_by_name.get(path.stem.lower(), RuleCategory.GENERAL)

    def _priority(self, path: Path, description: str) -> RulePriority:
        text = f"{path.stem} {description}".lower()
        if any(term in text for term in ("security", "forbidden", "anti-gravity", "nunca", "critical")):
            return RulePriority.CRITICAL
        if any(term in text for term in ("architecture", "testing", "qa", "siempre", "must")):
            return RulePriority.HIGH
        return RulePriority.NORMAL
