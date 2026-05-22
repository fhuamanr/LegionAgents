"""Observability application service for FastAPI adapters."""

from uuid import UUID

from app.schemas import AgentAnalyticsResponse, ObservabilitySnapshotResponse, WorkflowAnalyticsResponse
from app.services.execution_service import ExecutionService
from core.observability import ObservabilityService


class ObservabilityApplicationService:
    """FastAPI-facing observability service."""

    def __init__(
        self,
        execution_service: ExecutionService,
        observability: ObservabilityService | None = None,
    ) -> None:
        self._observability = observability or ObservabilityService(execution_service.event_bus)

    async def snapshot(self, workflow_id: UUID | None = None) -> ObservabilitySnapshotResponse:
        snapshot = await self._observability.snapshot(workflow_id=workflow_id)
        return ObservabilitySnapshotResponse(snapshot=snapshot.model_dump(mode="json"))

    async def workflow_analytics(self, workflow_id: UUID) -> WorkflowAnalyticsResponse:
        snapshot = await self._observability.snapshot(workflow_id=workflow_id)
        analytics = snapshot.workflow_analytics[0].model_dump(mode="json") if snapshot.workflow_analytics else {}
        return WorkflowAnalyticsResponse(workflow_id=workflow_id, analytics=analytics)

    async def agent_analytics(self) -> AgentAnalyticsResponse:
        snapshot = await self._observability.snapshot()
        return AgentAnalyticsResponse(
            agents=tuple(agent.model_dump(mode="json") for agent in snapshot.agent_analytics)
        )

    async def prometheus_text(self) -> str:
        await self._observability.snapshot()
        return await self._observability.prometheus_text()

    async def datadog_json(self) -> str:
        await self._observability.snapshot()
        return await self._observability.datadog_json()

    async def otel_spans(self) -> tuple[dict, ...]:
        await self._observability.snapshot()
        return await self._observability.otel_spans()

    def grafana_dashboard(self) -> dict:
        return self._observability.grafana.build()
