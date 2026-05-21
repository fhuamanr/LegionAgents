"""Requirement classification for ingested stories."""

from abc import ABC, abstractmethod

from core.contracts.ingestion import RequirementCategory, RequirementClassification


class RequirementClassifier(ABC):
    """Classification boundary for requirements."""

    @abstractmethod
    async def classify(self, text: str) -> RequirementClassification:
        """Classify requirement text."""


class KeywordRequirementClassifier(RequirementClassifier):
    """Deterministic keyword classifier suitable for local ingestion."""

    _signals: dict[RequirementCategory, tuple[str, ...]] = {
        RequirementCategory.SECURITY: ("auth", "permission", "role", "encrypt", "secret", "token", "security"),
        RequirementCategory.PERFORMANCE: ("latency", "throughput", "performance", "load", "scale", "response time"),
        RequirementCategory.DATA: ("data", "database", "schema", "record", "report", "analytics"),
        RequirementCategory.INTEGRATION: ("api", "webhook", "integration", "jira", "notion", "gitlab", "external"),
        RequirementCategory.UX: ("screen", "dashboard", "button", "user interface", "responsive", "accessibility"),
        RequirementCategory.TESTING: ("test", "qa", "coverage", "acceptance criteria", "validation"),
        RequirementCategory.NON_FUNCTIONAL: ("availability", "observability", "logging", "audit", "compliance"),
        RequirementCategory.FUNCTIONAL: ("as a", "i want", "so that", "user can", "system must"),
    }

    async def classify(self, text: str) -> RequirementClassification:
        haystack = text.lower()
        scores: dict[RequirementCategory, list[str]] = {}
        for category, keywords in self._signals.items():
            matches = [keyword for keyword in keywords if keyword in haystack]
            if matches:
                scores[category] = matches

        if not scores:
            return RequirementClassification(
                category=RequirementCategory.UNKNOWN,
                confidence=0.2,
                rationale="No known classification signals were detected.",
            )

        category, signals = max(scores.items(), key=lambda item: len(item[1]))
        confidence = min(0.95, 0.45 + (len(signals) * 0.15))
        return RequirementClassification(
            category=category,
            confidence=confidence,
            rationale=f"Detected {category.value} signals in requirement text.",
            signals=tuple(signals),
        )
