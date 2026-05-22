"""FastAPI adapter for security, RBAC, and audit services."""

from uuid import UUID

from app.schemas import (
    AccessCheckApiRequest,
    AccessCheckResponse,
    AuditEventCreateRequest,
    AuditEventListResponse,
    AuditEventResponse,
    TokenIssueApiRequest,
    TokenIssueResponse,
)
from core.contracts.security import (
    AccessCheckRequest,
    AuditEvent,
    AuditEventType,
    AuditQuery,
    AuthPrincipal,
    SecurityPermission,
    SecurityRole,
    TokenIssueRequest,
)
from core.security import AuditService, JWTService, RBACPolicy


class SecurityApplicationService:
    """Application service for local JWT auth, RBAC checks, and immutable audit."""

    def __init__(
        self,
        jwt: JWTService | None = None,
        rbac: RBACPolicy | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.jwt = jwt or JWTService()
        self.rbac = rbac or RBACPolicy()
        self.audit = audit or AuditService()

    async def issue_token(self, request: TokenIssueApiRequest) -> TokenIssueResponse:
        result = await self.jwt.issue(
            TokenIssueRequest(
                subject=request.subject,
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
                roles=tuple(SecurityRole(role) for role in request.roles),
                permissions=tuple(SecurityPermission(permission) for permission in request.permissions),
                expires_in_seconds=request.expires_in_seconds,
                metadata=request.metadata,
            )
        )
        await self.audit.record(
            AuditEvent(
                type=AuditEventType.AUTH_TOKEN_ISSUED,
                actor=result.principal.subject,
                tenant_id=result.principal.tenant_id,
                workspace_id=result.principal.workspace_id,
                action="issue_token",
                payload={"roles": [role.value for role in result.principal.roles]},
            )
        )
        return TokenIssueResponse(
            access_token=result.access_token,
            token_type=result.token_type,
            principal=result.principal.model_dump(mode="json"),
        )

    async def verify_token(self, token: str) -> AuthPrincipal:
        try:
            principal = await self.jwt.verify(token)
            await self.audit.record(
                AuditEvent(
                    type=AuditEventType.AUTH_TOKEN_VALIDATED,
                    actor=principal.subject,
                    tenant_id=principal.tenant_id,
                    workspace_id=principal.workspace_id,
                    action="validate_token",
                )
            )
            return principal
        except Exception:
            await self.audit.record(
                AuditEvent(type=AuditEventType.AUTH_TOKEN_REJECTED, action="validate_token", outcome="failed")
            )
            raise

    async def check_access(self, principal: AuthPrincipal, request: AccessCheckApiRequest) -> AccessCheckResponse:
        result = self.rbac.check(
            AccessCheckRequest(
                principal=principal,
                required_permissions=tuple(SecurityPermission(permission) for permission in request.required_permissions),
                any_permission=request.any_permission,
            )
        )
        if not result.allowed:
            await self.audit.record(
                AuditEvent(
                    type=AuditEventType.RBAC_DENIED,
                    actor=principal.subject,
                    tenant_id=principal.tenant_id,
                    workspace_id=principal.workspace_id,
                    action="check_access",
                    outcome="denied",
                    payload={"missing_permissions": [permission.value for permission in result.missing_permissions]},
                )
            )
        return AccessCheckResponse(
            allowed=result.allowed,
            missing_permissions=tuple(permission.value for permission in result.missing_permissions),
            granted_permissions=tuple(permission.value for permission in result.granted_permissions),
        )

    async def record_audit_event(self, request: AuditEventCreateRequest) -> AuditEventResponse:
        event = await self.audit.record(
            AuditEvent(
                type=AuditEventType(request.type),
                actor=request.actor,
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
                workflow_id=request.workflow_id,
                agent_name=request.agent_name,
                resource=request.resource,
                action=request.action,
                outcome=request.outcome,
                payload=request.payload,
            )
        )
        return AuditEventResponse(event=event.model_dump(mode="json"))

    async def query_audit_events(
        self,
        type: str | None = None,
        actor: str | None = None,
        tenant_id: str | None = None,
        workspace_id: UUID | None = None,
        workflow_id: UUID | None = None,
        agent_name: str | None = None,
        limit: int = 100,
    ) -> AuditEventListResponse:
        events = await self.audit.query(
            AuditQuery(
                type=AuditEventType(type) if type else None,
                actor=actor,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=workflow_id,
                agent_name=agent_name,
                limit=limit,
            )
        )
        return AuditEventListResponse(events=tuple(event.model_dump(mode="json") for event in events))
