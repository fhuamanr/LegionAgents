"""Immutable audit event persistence."""

import hashlib
import json
from abc import ABC, abstractmethod
from uuid import UUID

from core.contracts.security import AuditEvent, AuditQuery


class AuditRepository(ABC):
    """Audit persistence boundary."""

    @abstractmethod
    async def append(self, event: AuditEvent) -> AuditEvent:
        """Append an immutable audit event."""

    @abstractmethod
    async def query(self, query: AuditQuery) -> tuple[AuditEvent, ...]:
        """Query audit events."""


class InMemoryAuditRepository(AuditRepository):
    """Hash-chained in-memory audit repository."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._ids: set[UUID] = set()

    async def append(self, event: AuditEvent) -> AuditEvent:
        if event.id in self._ids:
            raise ValueError("Audit events are immutable and cannot be replaced")
        previous_hash = self._events[-1].event_hash if self._events else None
        event_hash = self._hash(event.model_copy(update={"previous_hash": previous_hash, "event_hash": None}))
        stored = event.model_copy(update={"previous_hash": previous_hash, "event_hash": event_hash})
        self._events.append(stored)
        self._ids.add(stored.id)
        return stored

    async def query(self, query: AuditQuery) -> tuple[AuditEvent, ...]:
        events = [
            event
            for event in self._events
            if (query.type is None or event.type == query.type)
            and (query.actor is None or event.actor == query.actor)
            and (query.tenant_id is None or event.tenant_id == query.tenant_id)
            and (query.workspace_id is None or event.workspace_id == query.workspace_id)
            and (query.workflow_id is None or event.workflow_id == query.workflow_id)
            and (query.agent_name is None or event.agent_name == query.agent_name)
        ]
        return tuple(events[-query.limit :])

    def _hash(self, event: AuditEvent) -> str:
        payload = event.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class AuditService:
    """High-level audit event recorder."""

    def __init__(self, repository: AuditRepository | None = None) -> None:
        self._repository = repository or InMemoryAuditRepository()

    async def record(self, event: AuditEvent) -> AuditEvent:
        return await self._repository.append(event)

    async def query(self, query: AuditQuery) -> tuple[AuditEvent, ...]:
        return await self._repository.query(query)
