from uuid import uuid4

import pytest

from core.observability import ObservabilityService
from core.streaming import ExecutionEventEmitter, ExecutionEventType, InMemoryExecutionEventBus


@pytest.mark.asyncio
async def test_observability_tracks_metrics_errors_tokens_prompts_and_analytics() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    service = ObservabilityService(bus)
    workflow_id = uuid4()

    await emitter.agent_started(workflow_id=workflow_id, agent_name="developer")
    await emitter.emit(
        ExecutionEventType.AGENT_COMPLETED,
        workflow_id=workflow_id,
        agent_name="developer",
        message="Developer completed.",
        payload={
            "duration_ms": 1250,
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            "prompt": {"message_count": 3, "character_count": 1200, "estimated_tokens": 300},
        },
    )
    await emitter.retry_started(workflow_id=workflow_id, agent_name="qa", attempt=2)
    await emitter.emit(
        ExecutionEventType.QA_FAILED,
        workflow_id=workflow_id,
        agent_name="qa",
        message="QA rejected implementation.",
    )

    snapshot = await service.snapshot(workflow_id=workflow_id)
    metric_names = {metric.name for metric in snapshot.metrics}

    assert "agent_executions_started_total" in metric_names
    assert "agent_execution_duration_ms" in metric_names
    assert "tokens_total" in metric_names
    assert "prompt_size_estimated_tokens" in metric_names
    assert snapshot.errors[0].message == "QA rejected implementation."
    assert snapshot.workflow_analytics[0].failures == 1
    assert snapshot.workflow_analytics[0].retries == 1
    assert snapshot.workflow_analytics[0].token_usage.total_tokens == 140
    assert snapshot.agent_analytics[0].agent_name == "developer"


@pytest.mark.asyncio
async def test_prometheus_datadog_otel_and_grafana_exporters_are_ready() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    service = ObservabilityService(bus)
    workflow_id = uuid4()

    await emitter.agent_started(workflow_id=workflow_id, agent_name="ba")
    await service.snapshot()

    prometheus = await service.prometheus_text()
    datadog = await service.datadog_json()
    otel = await service.otel_spans()
    grafana = service.grafana.build()

    assert "execution_events_total" in prometheus
    assert "series" in datadog
    assert otel[0]["name"] == "agent.ba"
    assert grafana["title"] == "Multi-Agent Delivery Observability"
