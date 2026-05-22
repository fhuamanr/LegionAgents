"""Dynamic governance management service."""

from uuid import UUID

from core.contracts.governance_management import (
    GovernanceConfigDocument,
    GovernanceConfigKind,
    GovernanceConfigScope,
    GovernanceConfigUpsert,
    GovernanceConfigVersion,
    GovernanceReloadEvent,
    GovernanceReloadStatus,
    GovernanceRollbackRequest,
)
from core.governance_management.reload import GovernanceReloadBus
from core.governance_management.repository import FileGovernanceConfigRepository, GovernanceConfigRepository


class GovernanceManagementService:
    """Coordinates editable governance config, version history, rollback, and reload."""

    def __init__(
        self,
        repository: GovernanceConfigRepository | None = None,
        reload_bus: GovernanceReloadBus | None = None,
    ) -> None:
        self._repository = repository or FileGovernanceConfigRepository()
        self._reload_bus = reload_bus or GovernanceReloadBus()

    async def save(self, request: GovernanceConfigUpsert) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion, GovernanceReloadEvent]:
        """Save a config document and emit reload metadata."""

        document, version = await self._repository.upsert(request)
        reload_event = await self._reload_bus.publish(
            GovernanceReloadEvent(
                document_id=document.id,
                version=document.version,
                status=GovernanceReloadStatus.APPLIED,
                message=f"Governance config reloaded: {document.name}",
                requested_by=request.updated_by,
                metadata={"kind": document.kind.value, "scope": document.scope.value, "agent_name": document.agent_name},
            )
        )
        return document, version, reload_event

    async def list(
        self,
        scope: GovernanceConfigScope | None = None,
        agent_name: str | None = None,
        kind: GovernanceConfigKind | None = None,
    ) -> tuple[GovernanceConfigDocument, ...]:
        """List governance documents."""

        return await self._repository.list(scope=scope, agent_name=agent_name, kind=kind)

    async def get(self, document_id: UUID) -> GovernanceConfigDocument:
        """Get one governance document."""

        return await self._repository.get(document_id)

    async def versions(self, document_id: UUID) -> tuple[GovernanceConfigVersion, ...]:
        """Get version history."""

        return await self._repository.versions(document_id)

    async def rollback(
        self,
        document_id: UUID,
        request: GovernanceRollbackRequest,
    ) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion, GovernanceReloadEvent]:
        """Rollback to a historical document version."""

        document, version = await self._repository.restore_version(
            document_id=document_id,
            target_version=request.target_version,
            updated_by=request.updated_by,
            change_summary=request.change_summary,
        )
        reload_event = await self._reload_bus.publish(
            GovernanceReloadEvent(
                document_id=document.id,
                version=document.version,
                status=GovernanceReloadStatus.APPLIED,
                message=f"Governance config rolled back: {document.name}",
                requested_by=request.updated_by,
                metadata={"rollback_to_version": request.target_version},
            )
        )
        return document, version, reload_event

    async def reload_history(self) -> tuple[GovernanceReloadEvent, ...]:
        """Return reload history."""

        return await self._reload_bus.history()
