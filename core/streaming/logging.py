"""Structured execution logging."""

import logging
from typing import Any
from uuid import UUID

from core.streaming.emitter import ExecutionEventEmitter
from core.streaming.models import ExecutionEvent, ExecutionEventType, ExecutionLogLevel


class StructuredExecutionLogger:
    """Emits structured logs to the event bus and optional Python logger."""

    def __init__(
        self,
        emitter: ExecutionEventEmitter,
        logger: logging.Logger | None = None,
    ) -> None:
        self._emitter = emitter
        self._logger = logger or logging.getLogger(__name__)

    async def log(
        self,
        level: ExecutionLogLevel,
        message: str,
        workflow_id: UUID | None = None,
        execution_id: UUID | None = None,
        agent_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ExecutionEvent:
        log_payload = {"level": level.value, **(payload or {})}
        self._logger.log(
            self._python_level(level),
            message,
            extra={"workflow_id": workflow_id, "execution_id": execution_id, "agent_name": agent_name},
        )
        return await self._emitter.emit(
            ExecutionEventType.LOG_EMITTED,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_name=agent_name,
            message=message,
            payload=log_payload,
        )

    def _python_level(self, level: ExecutionLogLevel) -> int:
        return {
            ExecutionLogLevel.DEBUG: logging.DEBUG,
            ExecutionLogLevel.INFO: logging.INFO,
            ExecutionLogLevel.WARNING: logging.WARNING,
            ExecutionLogLevel.ERROR: logging.ERROR,
            ExecutionLogLevel.CRITICAL: logging.CRITICAL,
        }[level]

