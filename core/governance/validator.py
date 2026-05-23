"""Policy validation and runtime enforcement."""

import json
import re
from typing import Any

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
        violations = self._forbidden_violations(policy, text)
        errors.extend(violations)
        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            metadata={
                "validated_rule_count": len(policy.rules),
                "forbidden_violation_count": len(violations),
            },
        )

    def validate_generated_output(
        self,
        policy: GovernancePolicy,
        agent_name: str,
        raw_output: str,
        structured_output: Any | None = None,
    ) -> GovernanceValidationResult:
        """Validate generated model output against active governance policy."""

        output_text = self._output_text(raw_output, structured_output)
        errors = list(self._forbidden_violations(policy, output_text))
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
                errors.append(f"Generated output violates required governance rule {rule.id}: {rule.description}")

        architecture_errors = self._architecture_violations(policy, agent_name, output_text, structured_output)
        errors.extend(architecture_errors)

        return GovernanceValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            metadata={
                "validated_rule_count": len(policy.rules),
                "enforced_required_rules": tuple(enforced_rules),
                "forbidden_violation_count": len(errors) - len(architecture_errors),
                "architecture_violation_count": len(architecture_errors),
            },
        )

    def _forbidden_violations(self, policy: GovernancePolicy, text: str) -> list[str]:
        violations: list[str] = []
        lowered = text.lower()
        for rule in policy.rules:
            if rule.effect != RuleEffect.FORBID:
                continue
            for pattern in self._forbidden_patterns(rule.description):
                if pattern.search(lowered):
                    violations.append(f"Runtime text violates {rule.id}: matched '{pattern.pattern}'")
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
    ) -> list[str]:
        if not any(rule.category == RuleCategory.ARCHITECTURE for rule in policy.rules):
            return []
        if agent_name != "developer" or structured_output is None:
            return []

        errors: list[str] = []
        code_changes = tuple(getattr(structured_output, "code_changes", tuple()) or tuple())
        for change in code_changes:
            path = str(getattr(change, "path", "")).lower()
            content = str(getattr(change, "content", "") or "").lower()
            combined = f"{path}\n{content}"
            if "controller" in path and re.search(r"\b(select\s+\*|repository|business|domain service)\b", content):
                errors.append(
                    "Generated output violates architecture governance: controller changes contain business, repository, or inline SQL logic."
                )
            if re.search(r"\bselect\s+\*\s+from\b", combined):
                errors.append("Generated output violates architecture governance: inline SQL detected in code changes.")
        return errors

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

