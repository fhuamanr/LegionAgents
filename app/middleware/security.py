"""Authentication context middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.security_service import SecurityApplicationService


class SecurityContextMiddleware(BaseHTTPMiddleware):
    """Parses optional bearer JWTs and attaches the principal to request state."""

    def __init__(self, app, security_service: SecurityApplicationService) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._security = security_service

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request.state.principal = None
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            try:
                request.state.principal = await self._security.verify_token(token)
            except Exception:
                request.state.principal = None
        response = await call_next(request)
        return response
