"""Security dependencies for route-level RBAC enforcement."""

import os
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.dependencies.container import get_security_service
from core.contracts.security import AccessCheckRequest, AuthPrincipal, SecurityPermission


def current_principal(request: Request) -> AuthPrincipal | None:
    return getattr(request.state, "principal", None)


def require_permissions(*permissions: SecurityPermission, any_permission: bool = False) -> Callable[[Request], AuthPrincipal]:
    async def dependency(request: Request) -> AuthPrincipal:
        principal = current_principal(request)
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        service = get_security_service()
        result = service.rbac.check(
            AccessCheckRequest(
                principal=principal,
                required_permissions=permissions,
                any_permission=any_permission,
            )
        )
        if not result.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return principal

    return dependency


def require_permissions_or_local_management(*permissions: SecurityPermission, any_permission: bool = False) -> Callable[[Request], AuthPrincipal | None]:
    async def dependency(request: Request) -> AuthPrincipal | None:
        principal = current_principal(request)
        if principal is None:
            enabled = os.getenv("ENABLE_LOCAL_MODEL_MANAGEMENT", "").strip().lower() in {"1", "true", "yes", "on"}
            if enabled:
                return None
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        service = get_security_service()
        result = service.rbac.check(
            AccessCheckRequest(
                principal=principal,
                required_permissions=permissions,
                any_permission=any_permission,
            )
        )
        if not result.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return principal

    return dependency
