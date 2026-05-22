"""Minimal JWT service using HMAC SHA-256.

This keeps core dependency-free for local development. Production deployments
can replace this with an enterprise IdP/JWKS verifier behind the same service
boundary.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from core.contracts.security import AuthPrincipal, SecurityPermission, SecurityRole, TokenIssueRequest, TokenIssueResult
from core.security.rbac import RBACPolicy


class JWTService:
    """Issues and verifies local JWTs."""

    def __init__(self, secret: str = "local-dev-secret", issuer: str = "ai-delivery-platform") -> None:
        self._secret = secret.encode("utf-8")
        self._issuer = issuer
        self._rbac = RBACPolicy()

    async def issue(self, request: TokenIssueRequest) -> TokenIssueResult:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=request.expires_in_seconds)
        principal = AuthPrincipal(
            subject=request.subject,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            roles=request.roles,
            permissions=request.permissions,
            issued_at=now,
            expires_at=expires,
            metadata=request.metadata,
        )
        enriched = principal.model_copy(update={"permissions": self._rbac.permissions_for(principal)})
        token = self._encode(
            {
                "iss": self._issuer,
                "sub": enriched.subject,
                "tenant_id": enriched.tenant_id,
                "workspace_id": str(enriched.workspace_id) if enriched.workspace_id else None,
                "roles": [role.value for role in enriched.roles],
                "permissions": [permission.value for permission in enriched.permissions],
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
                "metadata": enriched.metadata,
            }
        )
        return TokenIssueResult(access_token=token, principal=enriched)

    async def verify(self, token: str) -> AuthPrincipal:
        payload = self._decode(token)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ValueError("JWT has expired")
        return AuthPrincipal(
            subject=str(payload["sub"]),
            tenant_id=payload.get("tenant_id"),
            workspace_id=payload.get("workspace_id"),
            roles=tuple(SecurityRole(role) for role in payload.get("roles", [])),
            permissions=tuple(SecurityPermission(permission) for permission in payload.get("permissions", [])),
            issued_at=datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc),
            expires_at=expires_at,
            metadata=dict(payload.get("metadata", {})),
        )

    def _encode(self, payload: dict[str, Any]) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        signing_input = f"{self._b64_json(header)}.{self._b64_json(payload)}"
        signature = hmac.new(self._secret, signing_input.encode("utf-8"), hashlib.sha256).digest()
        return f"{signing_input}.{self._b64(signature)}"

    def _decode(self, token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        signing_input = f"{parts[0]}.{parts[1]}"
        expected = self._b64(hmac.new(self._secret, signing_input.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, parts[2]):
            raise ValueError("Invalid JWT signature")
        payload = json.loads(self._b64_decode(parts[1]).decode("utf-8"))
        if payload.get("iss") != self._issuer:
            raise ValueError("Invalid JWT issuer")
        return payload

    def _b64_json(self, payload: dict[str, Any]) -> str:
        return self._b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))

    def _b64(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    def _b64_decode(self, data: str) -> bytes:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii"))
