"""Centralized Agent Governance Engine."""

from pathlib import Path
import os
from typing import Any

from core.contracts.governance_management import GovernanceConfigKind, GovernanceConfigScope
from core.governance.inheritance import PolicyInheritanceEngine
from core.governance.loader import MarkdownPolicyLoader
from core.governance.models import GovernancePolicy, GovernanceRule, GovernanceValidationResult, RuleSource
from core.governance.registry import EnterpriseStandardsRegistry
from core.governance.validator import PolicyValidator
from core.governance_management.repository import GovernanceConfigRepository, PostgresGovernanceConfigRepository
from core.persistence import PostgresJsonDocumentStore


class AgentGovernanceEngine:
    """Facade for loading, merging, inheriting, and validating agent policies."""

    def __init__(
        self,
        agents_root: Path,
        standards_root: Path,
        inheritance_engine: PolicyInheritanceEngine | None = None,
        validator: PolicyValidator | None = None,
        runtime_config_repository: GovernanceConfigRepository | None = None,
    ) -> None:
        self._agents_root = agents_root
        self._standards_root = standards_root
        self._inheritance_engine = inheritance_engine or PolicyInheritanceEngine(
            standards_registry=EnterpriseStandardsRegistry(standards_root)
        )
        self._validator = validator or PolicyValidator()
        self._runtime_config_repository = runtime_config_repository or self._default_runtime_repository()
        self._runtime_loader = MarkdownPolicyLoader()

    async def effective_policy_for_agent(self, agent_name: str) -> GovernancePolicy:
        policy = await self._inheritance_engine.build_effective_policy(
            agent_name=agent_name,
            agent_policy_root=self._agents_root / agent_name,
        )
        runtime_rules = await self._runtime_rules(agent_name)
        if not runtime_rules:
            return policy
        rules_by_id = {rule.id: rule for rule in policy.rules}
        for rule in runtime_rules:
            rules_by_id[rule.id] = rule
        return policy.model_copy(
            update={
                "rules": tuple(sorted(rules_by_id.values(), key=lambda item: item.id)),
                "metadata": {
                    **policy.metadata,
                    "runtime_edited_rule_count": len(runtime_rules),
                    "effective_rule_count": len(rules_by_id),
                    "dynamic_policy_execution": True,
                },
            }
        )

    async def validate_agent_policy(self, agent_name: str) -> GovernanceValidationResult:
        policy = await self.effective_policy_for_agent(agent_name)
        return self._validator.validate_policy(policy)

    async def enforce_runtime_text(
        self,
        agent_name: str,
        text: str,
    ) -> GovernanceValidationResult:
        policy = await self.effective_policy_for_agent(agent_name)
        policy_result = self._validator.validate_policy(policy)
        runtime_result = self._validator.validate_runtime_text(policy, text)
        return GovernanceValidationResult(
            valid=policy_result.valid and runtime_result.valid,
            errors=policy_result.errors + runtime_result.errors,
            warnings=policy_result.warnings + runtime_result.warnings,
            metadata={
                "policy": policy.name,
                "policy_rule_count": len(policy.rules),
                **runtime_result.metadata,
            },
        )

    async def _runtime_rules(self, agent_name: str) -> tuple[GovernanceRule, ...]:
        if self._runtime_config_repository is None:
            return tuple()
        documents = tuple(await self._runtime_config_repository.list(scope=GovernanceConfigScope.GLOBAL)) + tuple(
            await self._runtime_config_repository.list(scope=GovernanceConfigScope.AGENT, agent_name=agent_name)
        )
        rules: list[GovernanceRule] = []
        for document in documents:
            if document.kind == GovernanceConfigKind.PROMPT:
                continue
            parsed = self._runtime_loader._rules_from_markdown(  # noqa: SLF001 - reuse the existing markdown rule parser.
                path=document.source_path or Path(f"runtime/{document.kind.value}.md"),
                scope=document.agent_name or document.scope.value,
                source=RuleSource.RUNTIME_EDITED,
            ) if document.source_path else self._rules_from_runtime_markdown(document)
            rules.extend(parsed)
        return tuple(rules)

    def _rules_from_runtime_markdown(self, document: Any) -> tuple[GovernanceRule, ...]:
        rules: list[GovernanceRule] = []
        for index, line in enumerate(document.markdown.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            description = stripped[2:].strip()
            if not description:
                continue
            path = Path(f"runtime/{document.kind.value}.md")
            rules.append(
                GovernanceRule(
                    id=f"runtime.{document.agent_name or document.scope.value}.{document.kind.value}.{index}",
                    description=description,
                    effect=self._runtime_loader._effect(path, description),  # noqa: SLF001
                    category=self._runtime_loader._category(path, document.agent_name or document.scope.value),  # noqa: SLF001
                    priority=self._runtime_loader._priority(path, description),  # noqa: SLF001
                    source=RuleSource.RUNTIME_EDITED,
                    allow_local_override=False,
                    metadata={
                        "document_id": str(document.id),
                        "document_version": document.version,
                        "kind": document.kind.value,
                        "scope": document.scope.value,
                        "line": index,
                    },
                )
            )
        return tuple(rules)

    def _default_runtime_repository(self) -> GovernanceConfigRepository | None:
        dsn = os.getenv("POSTGRES_DSN", "").strip()
        if not dsn:
            return None
        return PostgresGovernanceConfigRepository(PostgresJsonDocumentStore(dsn))

    async def validate_generated_output(
        self,
        agent_name: str,
        raw_output: str,
        structured_output: Any | None = None,
    ) -> GovernanceValidationResult:
        """Validate generated output and reject policy violations."""

        policy = await self.effective_policy_for_agent(agent_name)
        policy_result = self._validator.validate_policy(policy)
        output_result = self._validator.validate_generated_output(
            policy,
            agent_name=agent_name,
            raw_output=raw_output,
            structured_output=structured_output,
        )
        return GovernanceValidationResult(
            valid=policy_result.valid and output_result.valid,
            errors=policy_result.errors + output_result.errors,
            warnings=policy_result.warnings + output_result.warnings,
            metadata={
                "policy": policy.name,
                "policy_rule_count": len(policy.rules),
                **output_result.metadata,
            },
        )

