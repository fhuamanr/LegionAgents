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
        violations = self._filter_false_positive_forbidden_violations(
            violations=violations,
            agent_name=agent_name,
            output_text=output_text,
            structured_output=structured_output,
            enforcement_mode=mode,
        )
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
                    classification="blocking" if self._is_blocking(severity, mode) else "warning",
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
                            repairable="secret" in rule.id or "credential" in rule.id or "token" in rule.id,
                            classification="critical" if rule.severity == GovernanceSeverity.CRITICAL else ("blocking" if self._is_blocking(rule.severity, mode) else "warning"),
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
                    r"\b[a-z0-9_]*password[a-z0-9_]*\s*=",
                    r"\b[a-z0-9_]*secret[a-z0-9_]*\s*=",
                    r"\b[a-z0-9_]*token[a-z0-9_]*\s*=",
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
            patterns.extend(
                [
                    r"(controller|controllers).{0,120}(select\s+\*|insert\s+into|update\s+\w+\s+set|delete\s+from)",
                    r"(controller|controllers).{0,120}(import|from)\s+.*(repository|infra|infrastructure)",
                    r"(controller|controllers).{0,120}(new\s+\w*repository|repository\s*\()",
                    r"(controller|controllers).{0,120}(business logic|domain rule|domain service)",
                ]
            )
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
                        classification="blocking" if self._is_blocking(severity, mode) else "needs_review",
                        content_type="code",
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
                        classification="blocking" if self._is_blocking(severity, mode) else "needs_review",
                        content_type="code",
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

    def _filter_false_positive_forbidden_violations(
        self,
        *,
        violations: list[GovernanceViolation],
        agent_name: str,
        output_text: str,
        structured_output: Any | None,
        enforcement_mode: str,
    ) -> list[GovernanceViolation]:
        if agent_name != "developer":
            return violations
        filtered: list[GovernanceViolation] = []
        safe_phrases = (
            "should not",
            "must not",
            "avoid",
            "delegate to",
            "keep thin",
            "do not access",
            "no business logic",
        )
        controller_code = ""
        if structured_output is not None:
            for change in tuple(getattr(structured_output, "code_changes", tuple()) or tuple()):
                path = str(getattr(change, "path", "")).lower()
                content = str(getattr(change, "content", "") or "")
                if "controller" in path or "controllers" in path:
                    controller_code += "\n" + content
        for violation in violations:
            if violation.rule_id == "global.security.no-secret-exposure":
                filtered_secret = self._classify_secret_violation(
                    violation=violation,
                    structured_output=structured_output,
                    output_text=output_text,
                    enforcement_mode=enforcement_mode,
                )
                if filtered_secret is None:
                    continue
                filtered.append(filtered_secret)
                continue
            if "controller" not in violation.matched_text.lower():
                filtered.append(violation)
                continue
            context = output_text.lower()
            idx = context.find(violation.matched_text.lower())
            snippet = context[max(0, idx - 80) : idx + len(violation.matched_text) + 120] if idx >= 0 else context[:260]
            if any(phrase in snippet for phrase in safe_phrases):
                continue
            if controller_code.strip():
                if violation.matched_text.lower() not in controller_code.lower():
                    filtered.append(
                        violation.model_copy(
                            update={
                                "blocking": False,
                                "severity": GovernanceSeverity.WARNING,
                                "reason": f"{violation.reason} (downgraded: matched in non-code context)",
                                "content_type": "docs",
                            }
                        )
                    )
                    continue
                filtered.append(
                    violation.model_copy(
                        update={
                            "content_type": "code",
                            "blocking": self._is_blocking(violation.severity, enforcement_mode),
                        }
                    )
                )
                continue
            filtered.append(
                violation.model_copy(
                    update={
                        "blocking": False,
                        "severity": GovernanceSeverity.WARNING,
                        "reason": f"{violation.reason} (downgraded: no controller code evidence)",
                        "content_type": "docs",
                    }
                )
            )
        return filtered

    def _classify_secret_violation(
        self,
        *,
        violation: GovernanceViolation,
        structured_output: Any | None,
        output_text: str,
        enforcement_mode: str,
    ) -> GovernanceViolation | None:
        candidates: list[tuple[str, str, str]] = []
        if structured_output is not None:
            for change in tuple(getattr(structured_output, "code_changes", tuple()) or tuple()):
                path = str(getattr(change, "path", "")).strip()
                content = str(getattr(change, "content", "") or "")
                if path and content:
                    candidates.append((path, content, "code"))
            for test in tuple(getattr(structured_output, "tests", tuple()) or tuple()):
                path = str(getattr(test, "path", "")).strip()
                content = str(getattr(test, "content", "") or "")
                if path and content:
                    candidates.append((path, content, "test"))
        if not candidates:
            candidates.append(("", output_text, "docs"))

        secret_line = self._extract_secret_assignment_line(candidates)
        if secret_line is None:
            return violation
        path, line, content_type = secret_line
        key, value = self._split_secret_assignment(line)
        if self._is_password_field_usage(line):
            return None
        if self._is_placeholder_secret(value, path):
            return violation.model_copy(
                update={
                    "blocking": False,
                    "severity": GovernanceSeverity.WARNING,
                    "reason": f"{violation.reason} (downgraded: placeholder/example secret in template/docs context)",
                    "artifact_path": path,
                    "content_type": content_type,
                    "safe_phrase_detected": True,
                }
            )
        if content_type in {"docs", "test"} and not self._looks_like_real_secret(value):
            return violation.model_copy(
                update={
                    "blocking": False,
                    "severity": GovernanceSeverity.WARNING,
                    "reason": f"{violation.reason} (downgraded: non-runtime context)",
                    "artifact_path": path,
                    "content_type": content_type,
                    "safe_phrase_detected": True,
                }
            )
        return violation.model_copy(
            update={
                "blocking": self._is_blocking(violation.severity, enforcement_mode),
                "artifact_path": path,
                "content_type": content_type,
                "evidence": f"{key}=<redacted>",
                "matched_text": key,
                "repairable": True,
                "classification": "critical" if violation.severity == GovernanceSeverity.CRITICAL else ("blocking" if self._is_blocking(violation.severity, enforcement_mode) else "repairable"),
            }
        )

    def _extract_secret_assignment_line(self, candidates: list[tuple[str, str, str]]) -> tuple[str, str, str] | None:
        pattern = re.compile(r"(?im)^\s*([A-Z0-9_]*(?:PASSWORD|SECRET|API_KEY|TOKEN)[A-Z0-9_]*)\s*=\s*(.+?)\s*$")
        for path, content, ctype in candidates:
            for line in content.splitlines():
                if pattern.search(line):
                    return path, line.strip(), ctype
        return None

    def _split_secret_assignment(self, line: str) -> tuple[str, str]:
        if "=" not in line:
            return line.strip(), ""
        key, value = line.split("=", 1)
        return key.strip(), value.strip().strip('"').strip("'")

    def _is_password_field_usage(self, line: str) -> bool:
        lowered = line.lower()
        markers = ("field(", "basemodel", "input type='password'", "input type=\"password\"", "hash", "bcrypt", "argon2")
        return any(marker in lowered for marker in markers) or ":" in line and "=" not in line

    def _is_placeholder_secret(self, value: str, path: str) -> bool:
        lowered = (value or "").strip().lower()
        placeholder_tokens = (
            "",
            "example",
            "changeme",
            "change-me",
            "your_password",
            "your-password",
            "placeholder",
            "dummy",
            "test",
            "dev",
            "local",
            "postgres",
            "admin",
            "xxx",
            "****",
        )
        if lowered in placeholder_tokens:
            return True
        if lowered.startswith("<") and lowered.endswith(">"):
            return True
        if lowered.startswith("${") and lowered.endswith("}"):
            return True
        path_lower = (path or "").lower()
        if path_lower.endswith(".env.example") or "readme" in path_lower or "/docs/" in path_lower.replace("\\", "/"):
            if lowered and not self._looks_like_real_secret(lowered):
                return True
        return False

    def _looks_like_real_secret(self, value: str) -> bool:
        lowered = (value or "").strip().lower()
        if not lowered or len(lowered) < 8:
            return False
        if lowered.startswith("sk-live-") or lowered.startswith("sk-"):
            return True
        if any(ch.isdigit() for ch in lowered) and any(ch.isalpha() for ch in lowered) and any(ch in lowered for ch in ("@", "#", "$", "-", "_")):
            return True
        if lowered not in {"postgres", "admin", "password", "changeme", "change-me"} and len(lowered) >= 12:
            return True
        return False

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
        GovernanceSeverity.CRITICAL: 4,
    }
