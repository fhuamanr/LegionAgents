"""Autonomous PR validation layers."""

from abc import ABC, abstractmethod

from core.contracts.pr_review import (
    PRReviewCategory,
    PRReviewComment,
    PRReviewSeverity,
    PRValidationResult,
)
from core.contracts.repository_intelligence import RepositoryArchitecturePattern
from core.pr_review.context import PRReviewContext


class PRValidator(ABC):
    """Base interface for PR review validators."""

    category: PRReviewCategory

    @abstractmethod
    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        """Validate one PR review category."""

    def _result(self, comments: list[PRReviewComment], metadata: dict[str, object] | None = None) -> PRValidationResult:
        return PRValidationResult(
            category=self.category,
            passed=not any(comment.blocking for comment in comments),
            comments=tuple(comments),
            metadata=dict(metadata or {}),
        )


class ArchitecturePRValidator(PRValidator):
    """Validates architecture boundaries and architecture-sensitive changes."""

    category = PRReviewCategory.ARCHITECTURE

    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        comments: list[PRReviewComment] = []
        changed_paths = context.changed_paths
        intelligence = context.request.repository_intelligence
        patterns = {
            detection.pattern
            for detection in (intelligence.architecture if intelligence else tuple())
        }
        if RepositoryArchitecturePattern.CLEAN_ARCHITECTURE in patterns:
            if any(path.startswith("app/") for path in changed_paths) and any(path.startswith("core/") for path in changed_paths):
                comments.append(
                    PRReviewComment(
                        category=self.category,
                        severity=PRReviewSeverity.MEDIUM,
                        message="PR changes application and core layers together; verify dependency direction and boundary ownership.",
                        rule_id="architecture.layer-boundary-review",
                        recommendation="Keep orchestration/application concerns separate from core domain abstractions unless the contract change requires both.",
                    )
                )
        if any("core/contracts" in path.replace("\\", "/") for path in changed_paths) and not context.has_changed_path("tests/"):
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.HIGH,
                    message="Shared contract changes require focused tests to protect agent and API boundaries.",
                    rule_id="architecture.contract-tests-required",
                    recommendation="Add or update tests covering the changed contract behavior.",
                    blocking=True,
                )
            )
        return self._result(comments, {"detected_patterns": [pattern.value for pattern in patterns]})


class CodingStandardsPRValidator(PRValidator):
    """Validates coding standards using repository-aware heuristics."""

    category = PRReviewCategory.CODING_STANDARDS

    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        comments: list[PRReviewComment] = []
        for path in context.changed_source_files():
            content = context.read_changed_file(path)
            if path.endswith(".py") and "typing.Any" in content and "dict[str, Any]" not in content:
                comments.append(
                    PRReviewComment(
                        category=self.category,
                        severity=PRReviewSeverity.LOW,
                        path=path,
                        message="Broad Any usage detected; prefer explicit typed contracts where possible.",
                        rule_id="coding.typing-specificity",
                    )
                )
            if path.endswith(".py") and "async def" not in content and ("Service" in content or "Repository" in content):
                comments.append(
                    PRReviewComment(
                        category=self.category,
                        severity=PRReviewSeverity.INFO,
                        path=path,
                        message="Service or repository file has no async boundary.",
                        rule_id="coding.async-first-review",
                        recommendation="Confirm this component is intentionally synchronous.",
                    )
                )
        if context.diff.metadata.get("total_additions", 0) > 400:
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.MEDIUM,
                    message="Large PR detected; reviewability risk is elevated.",
                    rule_id="coding.pr-size",
                    recommendation="Consider splitting into smaller PRs if the changes are not tightly coupled.",
                )
            )
        return self._result(comments)


class QAPRValidator(PRValidator):
    """Validates QA readiness for changed source files."""

    category = PRReviewCategory.QA

    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        comments: list[PRReviewComment] = []
        source_files = context.changed_source_files()
        test_files = context.changed_test_files()
        if source_files and not test_files:
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.HIGH,
                    message="Source changes do not include corresponding automated tests.",
                    rule_id="qa.tests-required",
                    recommendation="Add unit, integration, or browser tests aligned to the changed behavior.",
                    blocking=True,
                    metadata={"source_file_count": len(source_files)},
                )
            )
        if context.has_changed_path("frontend/", "app/") and not context.has_changed_path(".spec.", ".test.", "playwright", "selenium"):
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.MEDIUM,
                    message="UI-facing changes should include browser automation or screenshot evidence.",
                    rule_id="qa.browser-evidence",
                    recommendation="Add Playwright/Selenium validation or attach generated QA evidence.",
                )
            )
        return self._result(comments, {"test_file_count": len(test_files)})


class SecurityPRValidator(PRValidator):
    """Validates security-sensitive PR risks."""

    category = PRReviewCategory.SECURITY

    _secret_markers = ("password=", "api_key", "secret", "token=", "private_key")

    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        comments: list[PRReviewComment] = []
        if "security_sensitive_files_changed" in context.diff.risk_flags or context.has_changed_path(".env"):
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.CRITICAL,
                    message="Security-sensitive files changed.",
                    rule_id="security.sensitive-files",
                    recommendation="Require security review before merge and verify no secrets are committed.",
                    blocking=True,
                )
            )
        for path in context.changed_source_files():
            content = context.read_changed_file(path).lower()
            if any(marker in content for marker in self._secret_markers):
                comments.append(
                    PRReviewComment(
                        category=self.category,
                        severity=PRReviewSeverity.CRITICAL,
                        path=path,
                        message="Potential secret or credential marker found in changed source.",
                        rule_id="security.secret-marker",
                        recommendation="Move secrets to managed configuration and rotate exposed values if needed.",
                        blocking=True,
                    )
                )
        return self._result(comments)


class DocumentationPRValidator(PRValidator):
    """Validates documentation readiness."""

    category = PRReviewCategory.DOCUMENTATION

    async def validate(self, context: PRReviewContext) -> PRValidationResult:
        comments: list[PRReviewComment] = []
        source_files = context.changed_source_files()
        docs_files = context.changed_documentation_files()
        if len(source_files) >= 3 and not docs_files:
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.MEDIUM,
                    message="Broad source changes do not include documentation updates.",
                    rule_id="docs.broad-change-docs",
                    recommendation="Update README, architecture notes, or generated documentation when behavior or platform surfaces change.",
                )
            )
        if context.pull_request and len(context.pull_request.description.strip()) < 30:
            comments.append(
                PRReviewComment(
                    category=self.category,
                    severity=PRReviewSeverity.LOW,
                    message="PR description is too short for enterprise review.",
                    rule_id="docs.pr-description",
                    recommendation="Include scope, validation, risks, and rollout notes.",
                )
            )
        return self._result(comments, {"documentation_file_count": len(docs_files)})
