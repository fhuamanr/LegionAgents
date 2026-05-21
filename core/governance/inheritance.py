"""Governance policy inheritance."""

from pathlib import Path

from core.governance.defaults import build_default_global_policy
from core.governance.loader import MarkdownPolicyLoader
from core.governance.merger import AgentPolicyMerger
from core.governance.models import GovernancePolicy, RuleSource
from core.governance.registry import EnterpriseStandardsRegistry


class PolicyInheritanceEngine:
    """Builds effective policies inherited by every agent."""

    def __init__(
        self,
        standards_registry: EnterpriseStandardsRegistry,
        policy_loader: MarkdownPolicyLoader | None = None,
        policy_merger: AgentPolicyMerger | None = None,
        global_policy: GovernancePolicy | None = None,
    ) -> None:
        self._standards_registry = standards_registry
        self._policy_loader = policy_loader or MarkdownPolicyLoader()
        self._policy_merger = policy_merger or AgentPolicyMerger()
        self._global_policy = global_policy or build_default_global_policy()

    async def build_effective_policy(
        self,
        agent_name: str,
        agent_policy_root: Path,
    ) -> GovernancePolicy:
        enterprise_policy = await self._standards_registry.load()
        local_policy = await self._policy_loader.load(
            root_path=agent_policy_root,
            scope=agent_name,
            source=RuleSource.AGENT_LOCAL,
        )
        return self._policy_merger.merge(
            global_policy=self._global_policy,
            enterprise_policy=enterprise_policy,
            local_policy=local_policy,
        )

