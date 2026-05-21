import asyncio
from uuid import uuid4

import pytest

from core.streaming import (
    ExecutionEvent,
    ExecutionEventEmitter,
    ExecutionEventType,
    ExecutionLogLevel,
    ExecutionTelemetryLayer,
    ExecutionTracker,
    InMemoryExecutionEventBus,
    StructuredExecutionLogger,
    TelemetrySink,
    TimelineGenerator,
)


class RecordingTelemetrySink(TelemetrySink):
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def record(self, event: ExecutionEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_event_bus_publishes_and_filters_history() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    workflow_id = uuid4()

    await emitter.agent_started(workflow_id=workflow_id, agent_name="developer")
    await emitter.agent_completed(workflow_id=workflow_id, agent_name="developer")
    await emitter.emit(ExecutionEventType.PR_GENERATED, workflow_id=workflow_id, agent_name="pr")
    await emitter.emit(ExecutionEventType.DOCS_GENERATED, workflow_id=workflow_id, agent_name="docs")

    history = await bus.history(workflow_id=workflow_id)
    completed = await bus.history(
        workflow_id=workflow_id,
        event_type=ExecutionEventType.AGENT_COMPLETED,
    )

    assert [event.type for event in history] == [
        ExecutionEventType.AGENT_STARTED,
        ExecutionEventType.AGENT_COMPLETED,
        ExecutionEventType.PR_GENERATED,
        ExecutionEventType.DOCS_GENERATED,
    ]
    assert len(completed) == 1


@pytest.mark.asyncio
async def test_event_bus_supports_live_subscription() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    workflow_id = uuid4()

    async def receive_one() -> ExecutionEvent:
        async for event in bus.subscribe(workflow_id=workflow_id):
            return event
        raise AssertionError("subscription ended unexpectedly")

    task = asyncio.create_task(receive_one())
    await asyncio.sleep(0)
    await emitter.agent_started(workflow_id=workflow_id, agent_name="qa")
    event = await asyncio.wait_for(task, timeout=1)

    assert event.type == ExecutionEventType.AGENT_STARTED
    assert event.agent_name == "qa"


@pytest.mark.asyncio
async def test_execution_tracker_updates_progress_and_failure_state() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    tracker = ExecutionTracker(bus)
    workflow_id = uuid4()

    await tracker.start_workflow(workflow_id=workflow_id, total_steps=2)
    started = await emitter.agent_started(workflow_id=workflow_id, agent_name="developer")
    completed = await emitter.agent_completed(workflow_id=workflow_id, agent_name="developer")
    failed = await emitter.emit(
        ExecutionEventType.QA_FAILED,
        workflow_id=workflow_id,
        agent_name="qa",
        message="QA rejected implementation.",
    )

    await tracker.apply_event(started)
    progress = await tracker.apply_event(completed)
    failed_progress = await tracker.apply_event(failed)

    assert progress is not None
    assert progress.completed_steps == 1
    assert progress.percent == 50.0
    assert failed_progress is not None
    assert failed_progress.failed is True


@pytest.mark.asyncio
async def test_timeline_generator_orders_events() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    workflow_id = uuid4()

    await emitter.agent_started(workflow_id=workflow_id, agent_name="ba")
    await emitter.retry_started(workflow_id=workflow_id, agent_name="developer", attempt=2)
    await emitter.agent_failed(workflow_id=workflow_id, agent_name="developer", error="boom")

    timeline = await TimelineGenerator(bus).generate(workflow_id)

    assert timeline.metadata["entry_count"] == 3
    assert [entry.event_type for entry in timeline.entries] == [
        ExecutionEventType.AGENT_STARTED,
        ExecutionEventType.RETRY_STARTED,
        ExecutionEventType.AGENT_FAILED,
    ]


@pytest.mark.asyncio
async def test_structured_logger_and_telemetry_sink() -> None:
    bus = InMemoryExecutionEventBus()
    emitter = ExecutionEventEmitter(bus)
    logger = StructuredExecutionLogger(emitter)
    sink = RecordingTelemetrySink()
    telemetry = ExecutionTelemetryLayer(bus, sinks=(sink,))
    workflow_id = uuid4()

    log_event = await logger.log(
        level=ExecutionLogLevel.INFO,
        message="Developer generated tests.",
        workflow_id=workflow_id,
        agent_name="developer",
    )
    telemetry_event = ExecutionEvent(
        type=ExecutionEventType.DOCS_GENERATED,
        workflow_id=workflow_id,
        agent_name="docs",
        message="Docs generated.",
    )
    await telemetry.record_event(telemetry_event)

    logs = await bus.history(workflow_id=workflow_id, event_type=ExecutionEventType.LOG_EMITTED)

    assert log_event.payload["level"] == "info"
    assert logs[0].message == "Developer generated tests."
    assert sink.events == [telemetry_event]

