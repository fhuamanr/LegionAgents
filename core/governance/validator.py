"""Policy validation and runtime enforcement."""

import json
import re
from typing import Any

from core.governance.models import (
    GovernanceSeverity,
    GovernancePolicy,
    GovernanceViolation,
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
        violations = self._forbidden_violations(policy, text, mode="strict")
        errors.extend(v.reason for v in violations if v.blocking)
        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            metadata={
                "validated_rule_count": len(policy.rules),
                "forbidden_violation_count": len(violations),
                "violations": tuple(v.model_dump(mode="json") for v in violations),
            },
        )

    def validate_generated_output(
        self,
        policy: GovernancePolicy,
        agent_name: str,
        raw_output: str,
        structured_output: Any | None = None,
        enforcement_mode: str = "balanced",
    ) -> GovernanceValidationResult:
        """Validate generated model output against active governance policy."""

        output_text = self._output_text(raw_output, structured_output)
        mode = enforcement_mode.strip().lower() or "balanced"
        violations: list[GovernanceViolation] = []
        violations.extend(self._forbidden_violations(policy, output_text, mode))
        warnings: list[str] = []
        enforced_rules: list[str] = []

        for rule in policy.rules:
            if rule.effect != RuleEffect.REQUIRE:
                continue
            check = self._required_check(rule.description)
            if check is None:
                continue
            enforced_rules.append(rule.id)
            if not self._required_check_passes(check, agent_name, output_text, structured_output):
                severity = self._effective_severity(rule, agent_name)
                reason = self._required_violation_reason(rule, check, agent_name)
                violation = GovernanceViolation(
                    rule_id=rule.id,
                    severity=severity,
                    evidence=self._best_evidence(output_text),
                    matched_text=self._best_evidence(output_text),
                    reason=reason,
                    suggested_fix="Adjust output to satisfy the required governance constraint.",
                    blocking=self._is_blocking(severity, mode),
                )
                if violation.blocking and self._weak_blocking_evidence(violation):
                    violation = violation.model_copy(
                        update={
                            "blocking": False,
                            "severity": GovernanceSeverity.WARNING,
                            "reason": f"{violation.reason} (downgraded: weak evidence)",
                        }
                    )
                violations.append(violation)
                if not violation.blocking:
                    warnings.append(violation.reason)

        architecture_violations = self._architecture_violations(
            policy, agent_name, output_text, structured_output, mode
        )
        violations.extend(architecture_violations)
        warnings.extend(v.reason for v in architecture_violations if not v.blocking)
        errors = [v.reason for v in violations if v.blocking]

        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            metadata={
                "validated_rule_count": len(policy.rules),
                "enforced_required_rules": tuple(enforced_rules),
                "forbidden_violation_count": len(
                    tuple(v for v in violations if "Runtime text violates" in v.reason)
                ),
                "architecture_violation_count": len(architecture_violations),
                "enforcement_mode": mode,
                "violations": tuple(v.model_dump(mode="json") for v in violations),
            },
        )

    def _forbidden_violations(
        self, policy: GovernancePolicy, text: str, mode: str = "balanced"
    ) -> list[GovernanceViolation]:
        violations: list[GovernanceViolation] = []
        lowered = text.lower()
        for rule in policy.rules:
            if rule.effect != RuleEffect.FORBID:
                continue
            for pattern in self._forbidden_patterns(rule.description):
                match = pattern.search(lowered)
                if match:
                    matched_text = match.group(0)
                    reason = f"Runtime text violates {rule.id}: matched '{pattern.pattern}'"
                    violations.append(
                        GovernanceViolation(
                            rule_id=rule.id,
                            severity=rule.severity,
                            evidence=matched_text,
                            matched_text=matched_text,
                            reason=reason,
                            suggested_fix="Remove forbidden content and follow policy guidance.",
                            blocking=self._is_blocking(rule.severity, mode),
                        )
                    )
        return violations

    def _forbidden_patterns(self, description: str) -> tuple[re.Pattern[str], ...]:
        text = description.lower()
        patterns: list[str] = []
        if "secret" in text or "credential" in text or "token" in text:
            patterns.extend(
                [
                    r"\bapi[_-]?key\s*=",
                    r"\bpassword\s*=",
                    r"\bsecret\s*=",
                    r"\btoken\s*=",
                    r"-----begin (rsa |ec |open)?private key-----",
                ]
            )
        if "monolithic" in text:
            patterns.append(r"\bmonolithic agent\b")
        if "sql inline" in text or "sql" in text:
            patterns.extend(
                [
                    r"\bselect\s+\*\s+from\b",
                    r"\binsert\s+into\s+\w+",
                    r"\bupdate\s+\w+\s+set\b",
                    r"\bdelete\s+from\s+\w+",
                ]
            )
        if "datetime.now" in text or "datetime.now" in text.replace(" ", ""):
            patterns.extend([r"\bdatetime\.now\s*\(", r"\bdate\.now\s*\("])
        if "magic string" in text:
            patterns.append(r"magic string")
        if "services est" in text or "static" in text:
            patterns.append(r"\bstatic\s+(service|class|readonly)\b")
        if "shared-kernel" in text or "shared kernel" in text:
            patterns.append(r"shared[-_ ]kernel")
        if "lógica en controllers" in text or "logic in controllers" in text or "controllers" in text:
            patterns.append(r"(controller|controllers).{0,160}(business|domain|repository|sql|use case|usecase)")
        return tuple(re.compile(pattern) for pattern in patterns)

    def _required_check(self, description: str) -> str | None:
        text = description.lower()
        if "test" in text or "prueba" in text:
            return "tests"
        if "validar entrada" in text or "validate external inputs" in text or "unsafe data" in text:
            return "input_validation"
        if "clean architecture" in text or "architecture boundaries" in text:
            return "clean_architecture"
        return None

    def _required_check_passes(
        self,
        check: str,
        agent_name: str,
        output_text: str,
        structured_output: Any | None,
    ) -> bool:
        lowered = output_text.lower()
        if check == "tests":
            if agent_name == "developer":
                return len(tuple(getattr(structured_output, "tests", tuple()) or tuple())) > 0
            if agent_name == "qa":
                has_qa_evidence = any(
                    (
                        getattr(structured_output, "test_reports", tuple()) or tuple(),
                        getattr(structured_output, "findings", tuple()) or tuple(),
                        getattr(structured_output, "bug_summaries", tuple()) or tuple(),
                    )
                ) or "test" in lowered or "prueba" in lowered
                return has_qa_evidence or bool(getattr(structured_output, "passed", False))
            return "test" in lowered or "prueba" in lowered
        if check == "input_validation":
            if agent_name not in {"developer", "architect"}:
                return True
            if agent_name == "architect":
                return any(
                    token in lowered
                    for token in (
                        "input validation",
                        "validate input",
                        "sanitize",
                        "payload validation",
                        "request validation",
                        "owasp",
                    )
                )
            implementation_text = self._implementation_text(structured_output).lower()
            if not implementation_text:
                implementation_text = lowered
            if not re.search(
                r"\b(request|input|payload|body|query|command|form|dto)\b",
                implementation_text,
            ):
                return True
            return any(
                term in implementation_text
                for term in ("validat", "sanitize", "pydantic", "field(", "guard", "unsafe data")
            )
        if check == "clean_architecture":
            return not any(
                pattern.search(lowered)
                for pattern in (
                    re.compile(r"(controller|router).{0,160}(business|domain|sql|repository)"),
                    re.compile(r"\bmonolithic\b"),
                )
            )
        return True

    def _architecture_violations(
        self,
        policy: GovernancePolicy,
        agent_name: str,
        output_text: str,
        structured_output: Any | None,
        mode: str = "balanced",
    ) -> list[GovernanceViolation]:
        if not any(rule.category == RuleCategory.ARCHITECTURE for rule in policy.rules):
            return []
        if agent_name != "developer" or structured_output is None:
            return []

        architecture_rule = next(
            (rule for rule in policy.rules if rule.id == "global.architecture.clean-boundaries"),
            None,
        )
        rule_id = architecture_rule.id if architecture_rule else "global.architecture.clean-boundaries"
        severity = architecture_rule.severity if architecture_rule else GovernanceSeverity.NEEDS_REVIEW

        errors: list[GovernanceViolation] = []
        code_changes = tuple(getattr(structured_output, "code_changes", tuple()) or tuple())
        for change in code_changes:
            path = str(getattr(change, "path", "")).lower()
            content = str(getattr(change, "content", "") or "").lower()
            combined = f"{path}\n{content}"
            if "controller" in path and re.search(r"\b(select\s+\*|repository|business|domain service)\b", content):
                reason = (
                    "Generated output violates architecture governance: controller changes contain "
                    "business, repository, or inline SQL logic."
                )
                errors.append(
                    GovernanceViolation(
                        rule_id=rule_id,
                        severity=severity,
                        evidence=f"path={path}",
                        matched_text=self._best_evidence(content),
                        reason=reason,
                        suggested_fix="Move orchestration/domain logic to use cases/services and keep controllers thin.",
                        blocking=self._is_blocking(severity, mode),
                    )
                )
            if re.search(r"\bselect\s+\*\s+from\b", combined):
                reason = "Generated output violates architecture governance: inline SQL detected in code changes."
                errors.append(
                    GovernanceViolation(
                        rule_id=rule_id,
                        severity=severity,
                        evidence=self._best_evidence(combined),
                        matched_text="select * from",
                        reason=reason,
                        suggested_fix="Move data access into repository/infrastructure boundaries.",
                        blocking=self._is_blocking(severity, mode),
                    )
                )
        return errors

    def _effective_severity(self, rule: Any, agent_name: str) -> GovernanceSeverity:
        rule_id = str(getattr(rule, "id", "")).lower()
        agent = (agent_name or "").lower()
        if agent == "architect" and rule_id in {
            "global.security.validate-input",
            "global.architecture.clean-boundaries",
            "global.architecture.layering",
            "global.quality.missing-tests",
            "global.docs.missing-docs",
        }:
            return GovernanceSeverity.WARNING
        if agent == "qa" and rule_id == "global.quality.missing-tests":
            return GovernanceSeverity.WARNING
        if agent == "docs" and rule_id == "global.docs.missing-docs":
            return GovernanceSeverity.WARNING
        return getattr(rule, "severity", GovernanceSeverity.BLOCKING)

    def _required_violation_reason(self, rule: Any, check: str, agent_name: str) -> str:
        if check == "input_validation" and agent_name.lower() == "architect":
            return (
                f"missing_security_consideration: {rule.id} is under-specified in architecture output. "
                "Add explicit input validation and unsafe data handling expectations."
            )
        return f"Generated output violates required governance rule {rule.id}: {rule.description}"

    def _weak_blocking_evidence(self, violation: GovernanceViolation) -> bool:
        evidence = (violation.evidence or "").strip()
        matched = (violation.matched_text or "").strip()
        if len(evidence) < 12 and len(matched) < 12:
            return True
        generic_markers = {"{}", "[]", "none", "n/a"}
        return evidence.lower() in generic_markers or matched.lower() in generic_markers

    def _is_blocking(self, severity: GovernanceSeverity, mode: str) -> bool:
        normalized = mode.strip().lower() if mode else "balanced"
        if normalized == "advisory":
            return False
        if normalized == "strict":
            return self._severity_rank[severity] >= self._severity_rank[GovernanceSeverity.NEEDS_REVIEW]
        return self._severity_rank[severity] >= self._severity_rank[GovernanceSeverity.BLOCKING]

    def _best_evidence(self, text: str, max_chars: int = 200) -> str:
        value = (text or "").strip().replace("\n", " ")
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 3] + "..."

    def _output_text(self, raw_output: str, structured_output: Any | None) -> str:
        if structured_output is None:
            return raw_output
        if hasattr(structured_output, "model_dump"):
            return raw_output + "\n" + json.dumps(structured_output.model_dump(mode="json"), default=str)
        return raw_output + "\n" + str(structured_output)

    def _implementation_text(self, structured_output: Any | None) -> str:
        if structured_output is None:
            return ""
        parts: list[str] = []
        for change in tuple(getattr(structured_output, "code_changes", tuple()) or tuple()):
            parts.append(str(getattr(change, "path", "")))
            parts.append(str(getattr(change, "description", "")))
            parts.append(str(getattr(change, "content", "") or ""))
        for work_item in tuple(getattr(structured_output, "work_items", tuple()) or tuple()):
            parts.append(str(getattr(work_item, "description", "")))
        return "\n".join(parts)

    _severity_rank = {
        GovernanceSeverity.INFO: 0,
        GovernanceSeverity.WARNING: 1,
        GovernanceSeverity.NEEDS_REVIEW: 2,
        GovernanceSeverity.BLOCKING: 3,
    }
