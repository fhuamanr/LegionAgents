"""Healthcheck APIs."""

from fastapi import APIRouter

from app.dependencies.container import get_provider_service
from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service="multi-agent-platform")


@router.get("/readiness")
async def readiness() -> dict[str, object]:
    provider_service = get_provider_service()
    provider_health = await provider_service.health()
    checks = provider_health.checks
    provider_ready = any(check["status"] == "ok" for check in checks)
    return {
        "status": "ready" if provider_ready else "degraded",
        "service": "multi-agent-platform",
        "checks": {
            "api": "ok",
            "provider_registry": "ok" if checks else "empty",
            "llm_provider": "ok" if provider_ready else "missing",
        },
        "providers": checks,
    }

