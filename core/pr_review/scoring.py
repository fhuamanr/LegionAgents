"""Merge readiness scoring for autonomous PR reviews."""

from core.contracts.pr_review import MergeReadiness, PRReviewComment, PRReviewScore, PRReviewSeverity


class PRScoringSystem:
    """Scores PR readiness from structured review comments."""

    _penalty_by_severity = {
        PRReviewSeverity.CRITICAL: 35.0,
        PRReviewSeverity.HIGH: 20.0,
        PRReviewSeverity.MEDIUM: 10.0,
        PRReviewSeverity.LOW: 4.0,
        PRReviewSeverity.INFO: 1.0,
    }

    def score(self, comments: tuple[PRReviewComment, ...]) -> PRReviewScore:
        blocking_count = sum(1 for comment in comments if comment.blocking)
        critical_count = self._count(comments, PRReviewSeverity.CRITICAL)
        high_count = self._count(comments, PRReviewSeverity.HIGH)
        medium_count = self._count(comments, PRReviewSeverity.MEDIUM)
        low_count = self._count(comments, PRReviewSeverity.LOW)
        penalty = sum(self._penalty_by_severity[comment.severity] for comment in comments)
        score = max(0.0, round(100.0 - penalty, 2))
        return PRReviewScore(
            score=score,
            readiness=self._readiness(score, blocking_count, critical_count, high_count),
            blocking_count=blocking_count,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            metadata={"comment_count": len(comments), "penalty": penalty},
        )

    def _readiness(
        self,
        score: float,
        blocking_count: int,
        critical_count: int,
        high_count: int,
    ) -> MergeReadiness:
        if blocking_count or critical_count:
            return MergeReadiness.BLOCKED
        if high_count or score < 75:
            return MergeReadiness.NEEDS_WORK
        if score < 95:
            return MergeReadiness.READY_WITH_WARNINGS
        return MergeReadiness.READY

    def _count(self, comments: tuple[PRReviewComment, ...], severity: PRReviewSeverity) -> int:
        return sum(1 for comment in comments if comment.severity == severity)
