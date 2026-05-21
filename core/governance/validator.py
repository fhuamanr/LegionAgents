"""Policy validation and runtime enforcement."""

from core.governance.models import (
    GovernancePolicy,
    GovernanceValidationResult,
    RuleCategory,
    RuleEffect,
)


class PolicyValidator:
    """Validates effective policies and runtime text against governance rules."""

    _required_categories = (
        RuleCategory.SECURITY,
        RuleCategory.CODING_STANDARDS,
        RuleCategory.ARCHITECTURE,
        RuleCategory.QA,
        RuleCategory.DOCUMENTATION,
    )

    def validate_policy(self, policy: GovernancePolicy) -> GovernanceValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        ids: set[str] = set()
        categories = {rule.category for rule in policy.rules}
        for rule in policy.rules:
            if rule.id in ids:
                errors.append(f"Duplicate governance rule id: {rule.id}")
            ids.add(rule.id)
            if not rule.description.strip():
                errors.append(f"Empty governance rule description: {rule.id}")

        for category in self._required_categories:
            if category not in categories:
                warnings.append(f"Missing governance category: {category.value}")

        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            metadata={"rule_count": len(policy.rules)},
        )

    def validate_runtime_text(
        self,
        policy: GovernancePolicy,
        text: str,
    ) -> GovernanceValidationResult:
        errors: list[str] = []
        lowered = text.lower()
        for rule in policy.rules:
            if rule.effect != RuleEffect.FORBID:
                continue
            forbidden_terms = self._forbidden_terms(rule.description)
            for term in forbidden_terms:
                if term in lowered:
                    errors.append(f"Runtime text violates {rule.id}: found '{term}'")
        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            metadata={"validated_rule_count": len(policy.rules)},
        )

    def _forbidden_terms(self, description: str) -> tuple[str, ...]:
        text = description.lower()
        terms: list[str] = []
        if "secret" in text or "credential" in text or "token" in text:
            terms.extend(["api_key=", "password=", "secret=", "token="])
        if "monolithic" in text:
            terms.append("monolithic agent")
        if "sql inline" in text or "sql" in text:
            terms.append("select * from")
        return tuple(terms)

