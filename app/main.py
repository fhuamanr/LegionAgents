"""FastAPI application factory."""

from fastapi import FastAPI

from app.middleware.request_id import RequestIdMiddleware
from app.routers import agents, executions, health, reports, uploads, workflows
from app.websocket.routes import router as websocket_router


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Enterprise Multi-Agent Software Delivery Platform",
        version="0.1.0",
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(workflows.router)
    app.include_router(executions.router)
    app.include_router(agents.router)
    app.include_router(reports.router)
    app.include_router(websocket_router)
    return app


app = create_app()

