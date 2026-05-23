"""Centralized Agent Governance Engine."""

from pathlib import Path
from typing import Any

from core.governance.inheritance import PolicyInheritanceEngine
from core.governance.models import GovernancePolicy, GovernanceValidationResult
from core.governance.registry import EnterpriseStandardsRegistry
from core.governance.validator import PolicyValidator


class AgentGovernanceEngine:
    """Facade for loading, merging, inheriting, and validating agent policies."""

    def __init__(
        self,
        agents_root: Path,
        standards_root: Path,
        inheritance_engine: PolicyInheritanceEngine | None = None,
        validator: PolicyValidator | None = None,
    ) -> None:
        self._agents_root = agents_root
        self._standards_root = standards_root
        self._inheritance_engine = inheritance_engine or PolicyInheritanceEngine(
            standards_registry=EnterpriseStandardsRegistry(standards_root)
        )
        self._validator = validator or PolicyValidator()

    async def effective_policy_for_agent(self, agent_name: str) -> GovernancePolicy:
        return await self._inheritance_engine.build_effective_policy(
            agent_name=agent_name,
            agent_policy_root=self._agents_root / agent_name,
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

