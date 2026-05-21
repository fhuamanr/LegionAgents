"""Execution event emitter."""

from typing import Any
from uuid import UUID

from core.streaming.bus import ExecutionEventBus
from core.streaming.models import ExecutionEvent, ExecutionEventType


class ExecutionEventEmitter:
    """Convenience API for emitting platform execution events."""

    def __init__(self, event_bus: ExecutionEventBus) -> None:
        self._event_bus = event_bus

    async def emit(
        self,
        event_type: ExecutionEventType,
        workflow_id: UUID | None = None,
        execution_id: UUID | None = None,
        thread_id: str | None = None,
        agent_name: str | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            type=event_type,
            workflow_id=workflow_id,
            execution_id=execution_id,
            thread_id=thread_id,
            agent_name=agent_name,
            message=message,
            payload=payload or {},
        )
        await self._event_bus.publish(event)
        return event

    async def agent_started(self, workflow_id: UUID, agent_name: str, execution_id: UUID | None = None) -> ExecutionEvent:
        return await self.emit(
            ExecutionEventType.AGENT_STARTED,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=agent_name,
            message=f"Agent started: {agent_name}",
        )

    async def agent_completed(self, workflow_id: UUID, agent_name: str, execution_id: UUID | None = None) -> ExecutionEvent:
        return await self.emit(
            ExecutionEventType.AGENT_COMPLETED,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=agent_name,
            message=f"Agent completed: {agent_name}",
        )

    async def agent_failed(
        self,
        workflow_id: UUID,
        agent_name: str,
        error: str,
        execution_id: UUID | None = None,
    ) -> ExecutionEvent:
        return await self.emit(
            ExecutionEventType.AGENT_FAILED,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=agent_name,
            message=f"Agent failed: {agent_name}",
            payload={"error": error},
        )

    async def retry_started(self, workflow_id: UUID, agent_name: str, attempt: int) -> ExecutionEvent:
        return await self.emit(
            ExecutionEventType.RETRY_STARTED,
            workflow_id=workflow_id,
            agent_name=agent_name,
            message=f"Retry started: {agent_name}",
            payload={"attempt": attempt},
        )

