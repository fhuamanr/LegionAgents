"""Default global governance policies."""

from core.governance.models import (
    GovernancePolicy,
    GovernanceRule,
    RuleCategory,
    RuleEffect,
    RulePriority,
    RuleSource,
)


def build_default_global_policy() -> GovernancePolicy:
    """Build global policies inherited by every agent."""

    return GovernancePolicy(
        name="Default Global Governance Policy",
        scope="global",
        rules=(
            GovernanceRule(
                id="global.security.no-secret-exposure",
                description="Never expose secrets, credentials, private keys, tokens, or environment values.",
                effect=RuleEffect.FORBID,
                category=RuleCategory.SECURITY,
                priority=RulePriority.CRITICAL,
                source=RuleSource.GLOBAL_DEFAULT,
            ),
            GovernanceRule(
                id="global.security.validate-input",
                description="Validate external inputs and handle unsafe data explicitly.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.SECURITY,
                priority=RulePriority.CRITICAL,
                source=RuleSource.GLOBAL_DEFAULT,
            ),
            GovernanceRule(
                id="global.architecture.clean-boundaries",
                description="Preserve Clean Architecture boundaries and keep orchestration separate from business logic.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.ARCHITECTURE,
                priority=RulePriority.CRITICAL,
                source=RuleSource.GLOBAL_DEFAULT,
            ),
            GovernanceRule(
                id="global.coding.typed-async",
                description="Use typed Python and async-first execution boundaries for runtime infrastructure.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.CODING_STANDARDS,
                priority=RulePriority.HIGH,
                source=RuleSource.GLOBAL_DEFAULT,
                allow_local_override=True,
            ),
            GovernanceRule(
                id="global.qa.minimum-evidence",
                description="QA outputs must include evidence, severity classification, and negative/edge validation when applicable.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.QA,
                priority=RulePriority.HIGH,
                source=RuleSource.GLOBAL_DEFAULT,
            ),
            GovernanceRule(
                id="global.documentation.required",
                description="User-facing capabilities must include concise documentation or generated documentation tasks.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.DOCUMENTATION,
                priority=RulePriority.NORMAL,
                source=RuleSource.GLOBAL_DEFAULT,
                allow_local_override=True,
            ),
            GovernanceRule(
                id="global.agent.no-responsibility-collapse",
                description="Never collapse specialized agent responsibilities into a monolithic agent.",
                effect=RuleEffect.FORBID,
                category=RuleCategory.AGENT_BOUNDARY,
                priority=RulePriority.CRITICAL,
                source=RuleSource.GLOBAL_DEFAULT,
            ),
        ),
    )

