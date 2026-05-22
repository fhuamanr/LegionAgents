"""Autonomous PR review engine."""

import logging

from core.contracts.pr_review import PRReviewReport, PRReviewRequest
from core.pr_review.context import PRReviewContext
from core.pr_review.scoring import PRScoringSystem
from core.pr_review.validators import (
    ArchitecturePRValidator,
    CodingStandardsPRValidator,
    DocumentationPRValidator,
    PRValidator,
    QAPRValidator,
    SecurityPRValidator,
)

logger = logging.getLogger(__name__)


class PRAnalysisEngine:
    """Coordinates automated repository-aware PR analysis."""

    def __init__(
        self,
        validators: tuple[PRValidator, ...] | None = None,
        scoring: PRScoringSystem | None = None,
    ) -> None:
        self._validators = validators or (
            ArchitecturePRValidator(),
            CodingStandardsPRValidator(),
            QAPRValidator(),
            SecurityPRValidator(),
            DocumentationPRValidator(),
        )
        self._scoring = scoring or PRScoringSystem()

    async def analyze(self, request: PRReviewRequest) -> PRReviewReport:
        """Analyze a pull request and return structured review output."""

        context = PRReviewContext(request)
        logger.info("pr_review.started", extra={"changed_file_count": len(context.changed_paths)})
        validations = tuple([await validator.validate(context) for validator in self._validators])
        comments = tuple(comment for validation in validations for comment in validation.comments)
        score = self._scoring.score(comments)
        logger.info(
            "pr_review.completed",
            extra={"comment_count": len(comments), "score": score.score, "readiness": score.readiness.value},
        )
        return PRReviewReport(
            title=request.title or (request.pull_request.title if request.pull_request else "Automated PR Review"),
            summary=self._summary(score.score, len(comments), score.readiness.value),
            score=score,
            comments=comments,
            validations=validations,
            metadata={
                "changed_file_count": len(context.changed_paths),
                "source_file_count": len(context.changed_source_files()),
                "test_file_count": len(context.changed_test_files()),
            },
        )

    def _summary(self, score: float, comment_count: int, readiness: str) -> str:
        return f"Automated PR review completed with score {score}/100, {comment_count} comments, readiness: {readiness}."
