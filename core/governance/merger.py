"""Agent policy merging."""

from core.governance.models import GovernancePolicy, GovernanceRule, RuleSource


class AgentPolicyMerger:
    """Merges global, enterprise, and local policies."""

    def merge(
        self,
        global_policy: GovernancePolicy,
        enterprise_policy: GovernancePolicy,
        local_policy: GovernancePolicy,
    ) -> GovernancePolicy:
        merged: dict[str, GovernanceRule] = {}
        for rule in global_policy.rules:
            merged[rule.id] = rule
        for rule in enterprise_policy.rules:
            merged[rule.id] = rule
        for rule in local_policy.rules:
            existing = merged.get(rule.id)
            if existing is None:
                merged[rule.id] = rule
                continue
            if existing.allow_local_override and rule.source == RuleSource.AGENT_LOCAL:
                merged[rule.id] = rule

        return GovernancePolicy(
            name=f"Effective Governance Policy: {local_policy.scope}",
            scope=local_policy.scope,
            rules=tuple(sorted(merged.values(), key=lambda item: item.id)),
            metadata={
                "global_rule_count": len(global_policy.rules),
                "enterprise_rule_count": len(enterprise_policy.rules),
                "local_rule_count": len(local_policy.rules),
                "effective_rule_count": len(merged),
            },
        )

