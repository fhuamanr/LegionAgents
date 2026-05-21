from pathlib import Path

import pytest

from core.governance import (
    AgentGovernanceEngine,
    AgentPolicyMerger,
    GovernancePolicy,
    GovernanceRule,
    MarkdownPolicyLoader,
    RuleCategory,
    RuleEffect,
    RulePriority,
    RuleSource,
)


@pytest.mark.asyncio
async def test_governance_engine_inherits_global_and_local_agent_rules() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )

    policy = await engine.effective_policy_for_agent("developer")
    rule_ids = {rule.id for rule in policy.rules}
    descriptions = [rule.description for rule in policy.rules]

    assert "global.security.no-secret-exposure" in rule_ids
    assert "global.agent.no-responsibility-collapse" in rule_ids
    assert any("NO usar SQL inline" in description for description in descriptions)
    assert policy.metadata["global_rule_count"] > 0
    assert policy.metadata["local_rule_count"] > 0


@pytest.mark.asyncio
async def test_markdown_policy_loader_classifies_qa_rules() -> None:
    loader = MarkdownPolicyLoader()

    policy = await loader.load(
        root_path=Path.cwd() / "agents" / "qa",
        scope="qa",
        source=RuleSource.AGENT_LOCAL,
    )

    assert any(rule.category == RuleCategory.QA for rule in policy.rules)
    assert any(rule.effect == RuleEffect.FORBID for rule in policy.rules)
    assert any(rule.priority == RulePriority.HIGH for rule in policy.rules)


def test_agent_policy_merger_allows_local_override_only_when_enabled() -> None:
    merger = AgentPolicyMerger()
    locked_rule = GovernanceRule(
        id="global.locked",
        description="Locked global rule",
        effect=RuleEffect.REQUIRE,
        allow_local_override=False,
    )
    overridable_rule = GovernanceRule(
        id="global.overridable",
        description="Original overridable rule",
        effect=RuleEffect.REQUIRE,
        allow_local_override=True,
    )
    local_locked = locked_rule.model_copy(
        update={
            "description": "Local locked override",
            "source": RuleSource.AGENT_LOCAL,
        }
    )
    local_overridable = overridable_rule.model_copy(
        update={
            "description": "Local allowed override",
            "source": RuleSource.AGENT_LOCAL,
        }
    )

    merged = merger.merge(
        global_policy=GovernancePolicy(
            name="global",
            scope="global",
            rules=(locked_rule, overridable_rule),
        ),
        enterprise_policy=GovernancePolicy(name="enterprise", scope="enterprise"),
        local_policy=GovernancePolicy(
            name="agent",
            scope="developer",
            rules=(local_locked, local_overridable),
        ),
    )
    by_id = {rule.id: rule for rule in merged.rules}

    assert by_id["global.locked"].description == "Locked global rule"
    assert by_id["global.overridable"].description == "Local allowed override"


@pytest.mark.asyncio
async def test_governance_engine_validates_runtime_text() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )

    result = await engine.enforce_runtime_text(
        agent_name="developer",
        text="password=123 should not be emitted",
    )

    assert result.valid is False
    assert any("global.security.no-secret-exposure" in error for error in result.errors)


@pytest.mark.asyncio
async def test_governance_engine_validates_effective_policy_shape() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )

    result = await engine.validate_agent_policy("qa")

    assert result.valid is True
    assert result.metadata["rule_count"] > 0
