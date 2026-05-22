"""Observability and telemetry APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.dependencies.container import get_observability_service
from app.schemas import AgentAnalyticsResponse, ObservabilitySnapshotResponse, WorkflowAnalyticsResponse
from app.services.observability_service import ObservabilityApplicationService

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/snapshot", response_model=ObservabilitySnapshotResponse)
async def get_observability_snapshot(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> ObservabilitySnapshotResponse:
    return await service.snapshot()


@router.get("/workflows/{workflow_id}", response_model=WorkflowAnalyticsResponse)
async def get_workflow_analytics(
    workflow_id: UUID,
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> WorkflowAnalyticsResponse:
    return await service.workflow_analytics(workflow_id)


@router.get("/agents", response_model=AgentAnalyticsResponse)
async def get_agent_analytics(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> AgentAnalyticsResponse:
    return await service.agent_analytics()


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> str:
    return await service.prometheus_text()


@router.get("/exporters/datadog", response_model=ObservabilitySnapshotResponse)
async def get_datadog_payload(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> ObservabilitySnapshotResponse:
    return ObservabilitySnapshotResponse(snapshot={"payload": await service.datadog_json()})


@router.get("/exporters/otel")
async def get_otel_spans(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> dict:
    return {"spans": await service.otel_spans()}


@router.get("/exporters/grafana")
async def get_grafana_dashboard(
    service: ObservabilityApplicationService = Depends(get_observability_service),
) -> dict:
    return service.grafana_dashboard()
