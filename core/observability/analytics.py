"""Workflow and agent analytics derived from execution events."""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from core.contracts.observability import AgentAnalytics, PromptTelemetry, TokenUsage, WorkflowAnalytics
from core.streaming.models import ExecutionEvent, ExecutionEventType


class ObservabilityAnalyticsEngine:
    """Builds workflow and agent analytics from execution events."""

    async def workflow_analytics(self, events: tuple[ExecutionEvent, ...]) -> tuple[WorkflowAnalytics, ...]:
        """Aggregate workflow analytics."""

        by_workflow: dict[UUID, list[ExecutionEvent]] = defaultdict(list)
        for event in events:
            if event.workflow_id is not None:
                by_workflow[event.workflow_id].append(event)

        analytics: list[WorkflowAnalytics] = []
        for workflow_id, workflow_events in by_workflow.items():
            analytics.append(self._workflow(workflow_id, tuple(workflow_events)))
        return tuple(analytics)

    async def agent_analytics(self, events: tuple[ExecutionEvent, ...]) -> tuple[AgentAnalytics, ...]:
        """Aggregate agent analytics."""

        by_agent: dict[str, list[ExecutionEvent]] = defaultdict(list)
        for event in events:
            if event.agent_name:
                by_agent[event.agent_name].append(event)

        return tuple(self._agent(agent_name, tuple(agent_events)) for agent_name, agent_events in sorted(by_agent.items()))

    def _workflow(self, workflow_id: UUID, events: tuple[ExecutionEvent, ...]) -> WorkflowAnalytics:
        started_at = min((event.timestamp for event in events), default=None)
        ended_at = max((event.timestamp for event in events), default=None)
        duration_ms = self._duration(started_at, ended_at)
        qa_failures = sum(1 for event in events if event.type == ExecutionEventType.QA_FAILED)
        qa_completions = sum(
            1
            for event in events
            if event.agent_name == "qa" and event.type in {ExecutionEventType.AGENT_COMPLETED, ExecutionEventType.QA_FAILED}
        )
        token_usage = self._token_usage(events)
        prompt_telemetry = self._prompt_telemetry(events)
        return WorkflowAnalytics(
            workflow_id=workflow_id,
            duration_ms=duration_ms,
            agent_count=len({event.agent_name for event in events if event.agent_name}),
            retries=sum(1 for event in events if event.type == ExecutionEventType.RETRY_STARTED),
            failures=sum(1 for event in events if event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}),
            qa_rejection_rate=(qa_failures / qa_completions) if qa_completions else 0,
            token_usage=token_usage,
            prompt_telemetry=prompt_telemetry,
            metadata={"event_count": len(events)},
        )

    def _agent(self, agent_name: str, events: tuple[ExecutionEvent, ...]) -> AgentAnalytics:
        durations = [
            float(event.payload["duration_ms"])
            for event in events
            if isinstance(event.payload.get("duration_ms"), int | float)
        ]
        token_usage = self._token_usage(events)
        prompt_telemetry = self._prompt_telemetry(events)
        return AgentAnalytics(
            agent_name=agent_name,
            executions_started=sum(1 for event in events if event.type == ExecutionEventType.AGENT_STARTED),
            executions_completed=sum(1 for event in events if event.type == ExecutionEventType.AGENT_COMPLETED),
            failures=sum(1 for event in events if event.type in {ExecutionEventType.AGENT_FAILED, ExecutionEventType.QA_FAILED}),
            retries=sum(1 for event in events if event.type == ExecutionEventType.RETRY_STARTED),
            qa_rejections=sum(1 for event in events if event.type == ExecutionEventType.QA_FAILED),
            average_execution_time_ms=round(sum(durations) / len(durations), 2) if durations else 0,
            token_usage=token_usage,
            prompt_telemetry=prompt_telemetry,
        )

    def _token_usage(self, events: tuple[ExecutionEvent, ...]) -> TokenUsage:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        for event in events:
            usage = event.payload.get("token_usage")
            if not isinstance(usage, dict):
                continue
            prompt_tokens += int(usage.get("prompt_tokens", 0))
            completion_tokens += int(usage.get("completion_tokens", 0))
            total_tokens += int(usage.get("total_tokens", 0))
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens or prompt_tokens + completion_tokens,
        )

    def _prompt_telemetry(self, events: tuple[ExecutionEvent, ...]) -> PromptTelemetry:
        message_count = 0
        character_count = 0
        estimated_tokens = 0
        for event in events:
            prompt = event.payload.get("prompt")
            if not isinstance(prompt, dict):
                continue
            message_count += int(prompt.get("message_count", 0))
            character_count += int(prompt.get("character_count", 0))
            estimated_tokens += int(prompt.get("estimated_tokens", 0))
        return PromptTelemetry(
            message_count=message_count,
            character_count=character_count,
            estimated_tokens=estimated_tokens,
        )

    def _duration(self, started_at: datetime | None, ended_at: datetime | None) -> float:
        if started_at is None or ended_at is None:
            return 0
        return round((ended_at - started_at).total_seconds() * 1000, 2)
