"""QA severity classification."""

from core.agents.qa.contracts import SeverityClassification
from core.contracts.outputs import OutputSeverity


class SeverityClassifier:
    """Rule-light severity classifier for local QA automation metadata."""

    async def classify(self, title: str, evidence: str) -> SeverityClassification:
        text = f"{title} {evidence}".lower()
        if any(term in text for term in ("security", "data loss", "crash", "critical")):
            return SeverityClassification(
                severity=OutputSeverity.CRITICAL,
                rationale="Evidence indicates critical impact.",
            )
        if any(term in text for term in ("broken", "failure", "blocked", "high")):
            return SeverityClassification(
                severity=OutputSeverity.HIGH,
                rationale="Evidence indicates a blocking or high-impact issue.",
            )
        if any(term in text for term in ("edge", "intermittent", "medium")):
            return SeverityClassification(
                severity=OutputSeverity.MEDIUM,
                rationale="Evidence indicates moderate risk.",
            )
        return SeverityClassification(
            severity=OutputSeverity.LOW,
            rationale="Evidence indicates low impact.",
        )

