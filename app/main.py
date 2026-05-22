"""FastAPI application factory."""

from fastapi import FastAPI

from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security import SecurityContextMiddleware
from app.routers import agents, approvals, chat, executions, governance_management, health, observability, prompt_studio, reports, security, uploads, workflows, workspace_management
from app.dependencies.container import (
    get_approval_service,
    get_chat_service,
    get_execution_service,
    get_observability_service,
    get_security_service,
)
from app.services.approval_service import ApprovalApplicationService
from app.services.chat_service import WorkspaceChatApplicationService
from app.services.execution_service import ExecutionService
from app.services.observability_service import ObservabilityApplicationService
from app.websocket.routes import router as websocket_router


def create_app(execution_service: ExecutionService | None = None) -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Enterprise Multi-Agent Software Delivery Platform",
        version="0.1.0",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityContextMiddleware, security_service=get_security_service())
    app.include_router(health.router)
    app.include_router(security.router)
    app.include_router(uploads.router)
    app.include_router(chat.router)
    app.include_router(workspace_management.router)
    app.include_router(workflows.router)
    app.include_router(executions.router)
    app.include_router(agents.router)
    app.include_router(approvals.router)
    app.include_router(governance_management.router)
    app.include_router(prompt_studio.router)
    app.include_router(observability.router)
    app.include_router(reports.router)
    app.include_router(websocket_router)
    if execution_service is not None:
        approval_service = ApprovalApplicationService(execution_service)
        observability_service = ObservabilityApplicationService(execution_service)
        chat_service = WorkspaceChatApplicationService(execution_service)
        app.dependency_overrides[get_execution_service] = lambda: execution_service
        app.dependency_overrides[get_approval_service] = lambda: approval_service
        app.dependency_overrides[get_observability_service] = lambda: observability_service
        app.dependency_overrides[get_chat_service] = lambda: chat_service
    return app


app = create_app()
