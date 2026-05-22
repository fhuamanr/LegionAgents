"""Security, RBAC, and audit contracts."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel, TraceMetadata


class SecurityPermission(StrEnum):
    """Enterprise platform permissions."""

    WORKSPACE_READ = "workspace:read"
    WORKSPACE_WRITE = "workspace:write"
    WORKFLOW_RUN = "workflow:run"
    WORKFLOW_READ = "workflow:read"
    APPROVAL_REVIEW = "approval:review"
    PROMPT_READ = "prompt:read"
    PROMPT_WRITE = "prompt:write"
    GOVERNANCE_READ = "governance:read"
    GOVERNANCE_WRITE = "governance:write"
    AUDIT_READ = "audit:read"
    SECURITY_ADMIN = "security:admin"


class SecurityRole(StrEnum):
    """Built-in RBAC roles."""

    PLATFORM_ADMIN = "platform_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    DELIVERY_LEAD = "delivery_lead"
    DEVELOPER = "developer"
    QA_LEAD = "qa_lead"
    VIEWER = "viewer"
    SERVICE_ACCOUNT = "service_account"


class AuditEventType(StrEnum):
    """Enterprise audit event types."""

    AUTH_TOKEN_ISSUED = "auth_token_issued"
    AUTH_TOKEN_VALIDATED = "auth_token_validated"
    AUTH_TOKEN_REJECTED = "auth_token_rejected"
    RBAC_DENIED = "rbac_denied"
    WORKFLOW_EXECUTION = "workflow_execution"
    AGENT_EXECUTION = "agent_execution"
    APPROVAL_DECISION = "approval_decision"
    PROMPT_CHANGED = "prompt_changed"
    PROMPT_ROLLED_BACK = "prompt_rolled_back"
    GOVERNANCE_CHANGED = "governance_changed"
    API_REQUEST = "api_request"


class AuthPrincipal(ContractBaseModel):
    """Authenticated principal claims."""

    subject: str = Field(min_length=1)
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    roles: tuple[SecurityRole, ...] = Field(default_factory=tuple)
    permissions: tuple[SecurityPermission, ...] = Field(default_factory=tuple)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenIssueRequest(ContractBaseModel):
    """Request to issue a local development JWT."""

    subject: str = Field(min_length=1)
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    roles: tuple[SecurityRole, ...] = Field(default_factory=tuple)
    permissions: tuple[SecurityPermission, ...] = Field(default_factory=tuple)
    expires_in_seconds: int = Field(default=3600, ge=60)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenIssueResult(ContractBaseModel):
    """Issued token response."""

    access_token: str
    token_type: str = "bearer"
    principal: AuthPrincipal


class AccessCheckRequest(ContractBaseModel):
    """RBAC access check request."""

    principal: AuthPrincipal
    required_permissions: tuple[SecurityPermission, ...] = Field(default_factory=tuple)
    any_permission: bool = False


class AccessCheckResult(ContractBaseModel):
    """RBAC access check result."""

    allowed: bool
    missing_permissions: tuple[SecurityPermission, ...] = Field(default_factory=tuple)
    granted_permissions: tuple[SecurityPermission, ...] = Field(default_factory=tuple)


class AuditEvent(ContractBaseModel):
    """Immutable audit event with hash-chain fields."""

    id: UUID = Field(default_factory=uuid4)
    type: AuditEventType
    actor: str = "anonymous"
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    workflow_id: UUID | None = None
    agent_name: str | None = None
    resource: str | None = None
    action: str = Field(min_length=1)
    outcome: str = Field(default="success", min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_hash: str | None = None
    event_hash: str | None = None


class AuditQuery(ContractBaseModel):
    """Audit event query."""

    type: AuditEventType | None = None
    actor: str | None = None
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    workflow_id: UUID | None = None
    agent_name: str | None = None
    limit: int = Field(default=100, ge=1)
