from core.runtime.context_governor import ContextGovernor
from core.contracts.prompts import PromptMessage, PromptRole
from core.contracts.artifacts import Artifact, ArtifactKind


def test_context_governor_enforces_local_ba_budget() -> None:
    governor = ContextGovernor()
    budget = governor.budget_for("ba", local_compact_mode=True)
    messages = (
        PromptMessage(role=PromptRole.SYSTEM, content="You are BA."),
        PromptMessage(role=PromptRole.USER, content="x" * 8000),
    )
    reduced, decision = governor.enforce_prompt_budget(messages, budget=budget.prompt_max_tokens)
    assert decision.prompt_tokens_before > budget.prompt_max_tokens
    assert decision.compressed is True
    assert len(reduced) == 2


def test_context_governor_blocks_when_still_oversized() -> None:
    governor = ContextGovernor()
    huge = (
        PromptMessage(role=PromptRole.SYSTEM, content="sys"),
        PromptMessage(role=PromptRole.USER, content="x" * 200_000),
    )
    _, decision = governor.enforce_prompt_budget(huge, budget=900)
    assert decision.blocked is True
    assert decision.reason == "oversized_prompt_blocked"


def test_context_governor_compact_handoff_trims_to_budget() -> None:
    governor = ContextGovernor()
    summary = "Summary " * 500
    handoff = governor.compact_handoff(
        agent_name="ba",
        summary=summary,
        metadata={"normalized_requirement": summary, "stories_summary": [summary, summary, summary]},
        max_tokens=120,
    )
    assert governor.estimate_tokens(handoff) <= 130


def test_context_governor_handoff_prefers_latest_artifacts() -> None:
    governor = ContextGovernor()
    artifacts = tuple(
        Artifact(
            id=f"a{i}",
            kind=ArtifactKind.GENERIC,
            name=f"artifact-{i}",
            producer_agent="architect" if i >= 3 else "ba",
            content=f"content-{i}",
        )
        for i in range(6)
    )
    compacted = governor.compact_artifacts_for_handoff(artifacts, max_items=3, max_chars_each=40)
    names = [a.name for a in compacted]
    assert names == ["artifact-3", "artifact-4", "artifact-5"]
