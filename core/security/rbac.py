"""Role-based access control."""

from core.contracts.security import AccessCheckRequest, AccessCheckResult, AuthPrincipal, SecurityPermission, SecurityRole


class RBACPolicy:
    """Built-in enterprise role-permission mapping."""

    _permissions_by_role: dict[SecurityRole, frozenset[SecurityPermission]] = {
        SecurityRole.PLATFORM_ADMIN: frozenset(SecurityPermission),
        SecurityRole.WORKSPACE_ADMIN: frozenset(
            {
                SecurityPermission.WORKSPACE_READ,
                SecurityPermission.WORKSPACE_WRITE,
                SecurityPermission.WORKFLOW_RUN,
                SecurityPermission.WORKFLOW_READ,
                SecurityPermission.APPROVAL_REVIEW,
                SecurityPermission.PROMPT_READ,
                SecurityPermission.PROMPT_WRITE,
                SecurityPermission.GOVERNANCE_READ,
            }
        ),
        SecurityRole.DELIVERY_LEAD: frozenset(
            {
                SecurityPermission.WORKSPACE_READ,
                SecurityPermission.WORKFLOW_RUN,
                SecurityPermission.WORKFLOW_READ,
                SecurityPermission.APPROVAL_REVIEW,
                SecurityPermission.PROMPT_READ,
            }
        ),
        SecurityRole.DEVELOPER: frozenset(
            {
                SecurityPermission.WORKSPACE_READ,
                SecurityPermission.WORKFLOW_READ,
                SecurityPermission.WORKFLOW_RUN,
                SecurityPermission.PROMPT_READ,
            }
        ),
        SecurityRole.QA_LEAD: frozenset(
            {
                SecurityPermission.WORKSPACE_READ,
                SecurityPermission.WORKFLOW_READ,
                SecurityPermission.APPROVAL_REVIEW,
                SecurityPermission.PROMPT_READ,
            }
        ),
        SecurityRole.VIEWER: frozenset(
            {
                SecurityPermission.WORKSPACE_READ,
                SecurityPermission.WORKFLOW_READ,
                SecurityPermission.PROMPT_READ,
                SecurityPermission.GOVERNANCE_READ,
            }
        ),
        SecurityRole.SERVICE_ACCOUNT: frozenset(SecurityPermission),
    }

    def permissions_for(self, principal: AuthPrincipal) -> tuple[SecurityPermission, ...]:
        permissions = set(principal.permissions)
        for role in principal.roles:
            permissions.update(self._permissions_by_role.get(role, frozenset()))
        return tuple(sorted(permissions, key=lambda item: item.value))

    def check(self, request: AccessCheckRequest) -> AccessCheckResult:
        granted = set(self.permissions_for(request.principal))
        required = set(request.required_permissions)
        if not required:
            return AccessCheckResult(allowed=True, granted_permissions=tuple(sorted(granted, key=lambda item: item.value)))
        if request.any_permission:
            allowed = bool(granted.intersection(required))
            missing = tuple() if allowed else tuple(sorted(required, key=lambda item: item.value))
        else:
            missing = tuple(sorted(required - granted, key=lambda item: item.value))
            allowed = not missing
        return AccessCheckResult(
            allowed=allowed,
            missing_permissions=missing,
            granted_permissions=tuple(sorted(granted, key=lambda item: item.value)),
        )
