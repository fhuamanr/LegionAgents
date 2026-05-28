from pathlib import Path

import pytest

from core.governance import (
    AgentGovernanceEngine,
    AgentPolicyMerger,
    GovernanceSeverity,
    GovernancePolicy,
    GovernanceRule,
    MarkdownPolicyLoader,
    RuleCategory,
    RuleEffect,
    RulePriority,
    RuleSource,
)
from core.governance.defaults import build_default_global_policy
from core.governance.validator import PolicyValidator
from core.contracts.outputs import CodeChangeProposal, DeveloperOutput, TestGenerationProposal


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


@pytest.mark.asyncio
async def test_governance_engine_rejects_developer_output_without_required_tests() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Implementation without tests",
        code_changes=(
            CodeChangeProposal(
                path="src/app.py",
                change_type="update",
                description="Update app",
                content="def hello() -> str:\n    return 'hello'\n",
            ),
        ),
    )

    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )

    assert result.valid is False
    assert any("agregar tests" in error for error in result.errors)


@pytest.mark.asyncio
async def test_governance_engine_rejects_forbidden_inline_sql_in_generated_output() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Implementation with forbidden SQL",
        code_changes=(
            CodeChangeProposal(
                path="src/orders/controller.py",
                change_type="update",
                description="Inline query",
                content="def list_orders():\n    return db.execute('select * from orders')\n",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_orders.py",
                test_type="unit",
                description="Covers orders",
                content="def test_orders():\n    assert True\n",
            ),
        ),
    )

    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )

    assert result.valid is False
    assert any("inline SQL" in error or "select" in error for error in result.errors)


def test_clean_boundaries_default_severity_is_needs_review() -> None:
    policy = build_default_global_policy()
    rule = next(rule for rule in policy.rules if rule.id == "global.architecture.clean-boundaries")
    assert rule.severity == GovernanceSeverity.NEEDS_REVIEW


def test_non_blocking_governance_issue_is_warning_in_balanced_mode() -> None:
    validator = PolicyValidator()
    policy = GovernancePolicy(
        name="runtime",
        scope="architect",
        rules=(
            GovernanceRule(
                id="global.architecture.clean-boundaries",
                description="Preserve Clean Architecture boundaries and keep orchestration separate from business logic.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.ARCHITECTURE,
                severity=GovernanceSeverity.NEEDS_REVIEW,
            ),
        ),
    )

    result = validator.validate_generated_output(
        policy=policy,
        agent_name="architect",
        raw_output="controller includes business logic and repository calls",
        structured_output=None,
        enforcement_mode="balanced",
    )

    assert result.valid is True
    assert not result.errors
    assert result.warnings


def test_clean_boundaries_is_non_blocking_for_architect_even_in_strict_mode() -> None:
    validator = PolicyValidator()
    policy = GovernancePolicy(
        name="runtime",
        scope="architect",
        rules=(
            GovernanceRule(
                id="global.architecture.clean-boundaries",
                description="Preserve Clean Architecture boundaries and keep orchestration separate from business logic.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.ARCHITECTURE,
                severity=GovernanceSeverity.NEEDS_REVIEW,
            ),
        ),
    )

    result = validator.validate_generated_output(
        policy=policy,
        agent_name="architect",
        raw_output="controller routes contain business logic and repository access",
        structured_output=None,
        enforcement_mode="strict",
    )

    assert result.valid is True
    assert not result.errors
    assert result.warnings


def test_validate_input_is_warning_not_blocking_for_architect_in_balanced_mode() -> None:
    validator = PolicyValidator()
    policy = GovernancePolicy(
        name="runtime",
        scope="architect",
        rules=(
            GovernanceRule(
                id="global.security.validate-input",
                description="Validate external inputs and handle unsafe data explicitly.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.SECURITY,
                severity=GovernanceSeverity.BLOCKING,
            ),
        ),
    )

    result = validator.validate_generated_output(
        policy=policy,
        agent_name="architect",
        raw_output="Architecture with modules and APIs, but no explicit security validation section.",
        structured_output=None,
        enforcement_mode="balanced",
    )

    assert result.valid is True
    assert not result.errors
    assert any("missing_security_consideration" in warning for warning in result.warnings)


def test_missing_validation_mention_is_warning_not_violation_for_architect() -> None:
    validator = PolicyValidator()
    policy = GovernancePolicy(
        name="runtime",
        scope="architect",
        rules=(
            GovernanceRule(
                id="global.security.validate-input",
                description="Validate external inputs and handle unsafe data explicitly.",
                effect=RuleEffect.REQUIRE,
                category=RuleCategory.SECURITY,
                severity=GovernanceSeverity.BLOCKING,
            ),
        ),
    )

    result = validator.validate_generated_output(
        policy=policy,
        agent_name="architect",
        raw_output="{}",
        structured_output=None,
        enforcement_mode="balanced",
    )

    assert result.valid is True
    assert not result.errors
    assert any("missing_security_consideration" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_hardcoded_secret_still_blocks_developer() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Introduces unsafe token in code",
        code_changes=(
            CodeChangeProposal(
                path="src/auth/config.py",
                change_type="update",
                description="Adds token",
                content="API_KEY='super-secret-token'",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_auth.py",
                test_type="unit",
                description="Auth tests",
                content="def test_auth():\n    assert True\n",
            ),
        ),
    )

    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )
    assert result.valid is False
    assert any("global.security.no-secret-exposure" in error for error in result.errors)


@pytest.mark.asyncio
async def test_developer_safe_controller_guidance_does_not_fail() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Architecture guidance text",
        code_changes=(
            CodeChangeProposal(
                path="docs/implementation_summary.md",
                change_type="create",
                description="Guidance",
                content="Controllers should not contain business logic and should delegate to use cases.",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_architecture.py",
                test_type="unit",
                description="doc coverage",
                content="def test_docs(): assert True\n",
            ),
        ),
    )
    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )
    assert result.valid is True


@pytest.mark.asyncio
async def test_developer_controller_sql_code_can_trigger_blocking() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Bad controller implementation",
        code_changes=(
            CodeChangeProposal(
                path="backend/src/api/controllers/orders_controller.py",
                change_type="update",
                description="Inline SQL in controller",
                content="def list_orders():\n    return db.execute('select * from orders')\n",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_orders.py",
                test_type="unit",
                description="orders",
                content="def test_orders(): assert True\n",
            ),
        ),
    )
    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )
    assert result.valid is False


@pytest.mark.asyncio
async def test_env_example_placeholder_password_does_not_block() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Env template",
        code_changes=(
            CodeChangeProposal(
                path="generated_project/.env.example",
                change_type="create",
                description="env template",
                content="DATABASE_PASSWORD=changeme\nPOSTGRES_PASSWORD=postgres\nJWT_SECRET=<your-jwt-secret>\n",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_env.py",
                test_type="unit",
                description="env",
                content="def test_env(): assert True\n",
            ),
        ),
    )
    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )
    assert result.valid is True


@pytest.mark.asyncio
async def test_real_secret_still_blocks_without_repair() -> None:
    engine = AgentGovernanceEngine(
        agents_root=Path.cwd() / "agents",
        standards_root=Path.cwd() / "repository" / "standards",
    )
    output = DeveloperOutput(
        agent_name="developer",
        summary="Real secret in source",
        code_changes=(
            CodeChangeProposal(
                path="backend/src/config.py",
                change_type="update",
                description="bad secret",
                content="DATABASE_PASSWORD=myRealPass123\n",
            ),
        ),
        tests=(
            TestGenerationProposal(
                path="tests/test_cfg.py",
                test_type="unit",
                description="cfg",
                content="def test_cfg(): assert True\n",
            ),
        ),
    )
    result = await engine.validate_generated_output(
        agent_name="developer",
        raw_output=output.model_dump_json(),
        structured_output=output,
    )
    assert result.valid is False
