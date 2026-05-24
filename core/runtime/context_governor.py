"""Context governor for per-agent budget enforcement and handoff compression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.contracts.artifacts import Artifact
from core.contracts.prompts import PromptMessage


@dataclass(frozen=True, slots=True)
class AgentBudget:
    prompt_max_tokens: int
    output_max_tokens: int
    handoff_max_tokens: int


@dataclass(frozen=True, slots=True)
class ContextGovernorDecision:
    prompt_tokens_before: int
    prompt_tokens_after: int
    budget: int
    compressed: bool
    blocked: bool
    reason: str | None = None


class ContextGovernor:
    """Estimate, compress, and gate prompt/handoff budgets before provider calls."""

    _local_budgets: dict[str, AgentBudget] = {
        "ba": AgentBudget(prompt_max_tokens=900, output_max_tokens=450, handoff_max_tokens=500),
        "architect": AgentBudget(prompt_max_tokens=1200, output_max_tokens=600, handoff_max_tokens=700),
        "developer": AgentBudget(prompt_max_tokens=1500, output_max_tokens=700, handoff_max_tokens=700),
        "qa": AgentBudget(prompt_max_tokens=1000, output_max_tokens=500, handoff_max_tokens=500),
        "docs": AgentBudget(prompt_max_tokens=900, output_max_tokens=500, handoff_max_tokens=400),
        "pr": AgentBudget(prompt_max_tokens=700, output_max_tokens=300, handoff_max_tokens=300),
    }

    def budget_for(self, agent_name: str, *, local_compact_mode: bool, overrides: dict[str, Any] | None = None) -> AgentBudget:
        if overrides:
            return AgentBudget(
                prompt_max_tokens=int(overrides.get("max_prompt_tokens", self._local_budgets.get(agent_name, self._local_budgets["architect"]).prompt_max_tokens)),
                output_max_tokens=int(overrides.get("max_output_tokens", self._local_budgets.get(agent_name, self._local_budgets["architect"]).output_max_tokens)),
                handoff_max_tokens=int(overrides.get("handoff_summary_max_tokens", self._local_budgets.get(agent_name, self._local_budgets["architect"]).handoff_max_tokens)),
            )
        if local_compact_mode:
            return self._local_budgets.get(agent_name, AgentBudget(1200, 600, 500))
        return AgentBudget(4000, 1500, 1000)

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def estimate_messages(self, messages: tuple[PromptMessage, ...]) -> int:
        return sum(self.estimate_tokens(message.content) for message in messages)

    def enforce_prompt_budget(
        self,
        messages: tuple[PromptMessage, ...],
        *,
        budget: int,
    ) -> tuple[tuple[PromptMessage, ...], ContextGovernorDecision]:
        before = self.estimate_messages(messages)
        if before <= budget:
            return messages, ContextGovernorDecision(before, before, budget, compressed=False, blocked=False)
        # Compress by truncating user message first.
        compressed = list(messages)
        user_index = next((index for index, message in enumerate(compressed) if message.role.value == "user"), len(compressed) - 1)
        base = compressed[user_index].content
        ratio = max(0.2, budget / max(before, 1))
        keep_chars = max(300, int(len(base) * ratio))
        compact = base[:keep_chars] + "\n\n[Context compressed by governor.]"
        compressed[user_index] = compressed[user_index].model_copy(update={"content": compact})
        final = tuple(compressed)
        after = self.estimate_messages(final)
        if after > budget:
            return final, ContextGovernorDecision(before, after, budget, compressed=True, blocked=True, reason="oversized_prompt_blocked")
        return final, ContextGovernorDecision(before, after, budget, compressed=True, blocked=False)

    def compact_handoff(
        self,
        *,
        agent_name: str,
        summary: str,
        metadata: dict[str, Any],
        max_tokens: int,
    ) -> str:
        lines = [f"AGENT: {agent_name}", f"SUMMARY: {summary.strip()[:400]}"]
        if agent_name == "ba":
            lines.append(f"NORMALIZED_REQUIREMENT: {str(metadata.get('normalized_requirement', summary))[:500]}")
            stories = metadata.get("stories_summary", [])
            for item in list(stories)[:3]:
                lines.append(f"STORY: {str(item)[:160]}")
        for key in ("assumptions", "constraints", "risks", "dependencies"):
            values = metadata.get(key, [])
            if isinstance(values, (list, tuple)):
                for item in list(values)[:3]:
                    lines.append(f"{key.upper()[:-1]}: {str(item)[:140]}")
        text = "\n".join(lines)
        if self.estimate_tokens(text) <= max_tokens:
            return text
        target_chars = max(200, max_tokens * 4)
        return text[:target_chars]

    def compact_artifacts_for_handoff(
        self,
        artifacts: tuple[Artifact, ...],
        *,
        max_items: int = 3,
        max_chars_each: int = 320,
    ) -> tuple[Artifact, ...]:
        compacted: list[Artifact] = []
        for artifact in artifacts[:max_items]:
            compacted.append(
                artifact.model_copy(
                    update={
                        "content": (artifact.content or "")[:max_chars_each],
                        "metadata": {**artifact.metadata, "compressed_handoff": True},
                    }
                )
            )
        return tuple(compacted)
