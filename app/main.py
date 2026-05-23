"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security import SecurityContextMiddleware
from app.routers import agents, approvals, chat, dashboard, executions, governance_management, health, observability, prompt_studio, providers, reports, security, uploads, workflows, workspace_management
from app.dependencies.container import (
    get_approval_service,
    get_chat_service,
    get_container,
    get_execution_service,
    get_observability_service,
    get_security_service,
)
from app.services.approval_service import ApprovalApplicationService
from app.services.chat_service import WorkspaceChatApplicationService
from app.services.execution_service import ExecutionService
from app.services.observability_service import ObservabilityApplicationService
from app.websocket.routes import router as websocket_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = get_container()
    await container.governance_management_service.ensure_seeded()
    await container.prompt_studio_service.ensure_seeded()
    providers = await container.provider_service.list()
    governance = await container.governance_management_service.list()
    prompts = await container.prompt_studio_service.list()
    logger.info("providers loaded: %s", len(providers.providers))
    logger.info("governance docs loaded: %s", len(governance.documents))
    logger.info("prompt docs loaded: %s", len(prompts.prompts))
    logger.info("config directory loaded: %s", Path.cwd())
    logger.info("upload directory: %s", Path(os.getenv("UPLOAD_ROOT", "outputs/uploads")).resolve())
    logger.info("artifact directory: %s", Path(os.getenv("STORAGE_ROOT", "outputs")).resolve())
    logger.info("workspace directory: %s", Path(os.getenv("WORKSPACE_ROOT", "workflows")).resolve())
    yield


def create_app(execution_service: ExecutionService | None = None) -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Enterprise Multi-Agent Software Delivery Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityContextMiddleware, security_service=get_security_service())
    app.include_router(health.router)
    app.include_router(security.router)
    app.include_router(uploads.router)
    app.include_router(chat.router)
    app.include_router(workspace_management.router)
    app.include_router(workflows.router)
    app.include_router(dashboard.router)
    app.include_router(executions.router)
    app.include_router(agents.router)
    app.include_router(approvals.router)
    app.include_router(governance_management.router)
    app.include_router(prompt_studio.router)
    app.include_router(providers.router)
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
