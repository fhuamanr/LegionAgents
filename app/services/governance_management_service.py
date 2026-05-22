"""Governance management application service."""

from uuid import UUID

from app.schemas import (
    GovernanceConfigListResponse,
    GovernanceConfigResponse,
    GovernanceConfigUpsertRequest,
    GovernanceReloadHistoryResponse,
    GovernanceRollbackApiRequest,
    GovernanceVersionListResponse,
)
from core.contracts.governance_management import (
    GovernanceConfigKind,
    GovernanceConfigScope,
    GovernanceConfigUpsert,
    GovernanceRollbackRequest,
)
from core.governance_management import GovernanceManagementService


class GovernanceManagementApplicationService:
    """FastAPI adapter for dynamic governance management."""

    def __init__(self, service: GovernanceManagementService | None = None) -> None:
        self._service = service or GovernanceManagementService()

    async def save(self, request: GovernanceConfigUpsertRequest) -> GovernanceConfigResponse:
        document, version, reload_event = await self._service.save(
            GovernanceConfigUpsert(
                scope=GovernanceConfigScope(request.scope),
                kind=GovernanceConfigKind(request.kind),
                name=request.name,
                markdown=request.markdown,
                agent_name=request.agent_name,
                updated_by=request.updated_by,
                change_summary=request.change_summary,
                metadata=request.metadata,
            )
        )
        return GovernanceConfigResponse(
            document=document.model_dump(mode="json"),
            latest_version=version.model_dump(mode="json"),
            reload_event=reload_event.model_dump(mode="json"),
        )

    async def list(
        self,
        scope: str | None = None,
        agent_name: str | None = None,
        kind: str | None = None,
    ) -> GovernanceConfigListResponse:
        documents = await self._service.list(
            scope=GovernanceConfigScope(scope) if scope else None,
            agent_name=agent_name,
            kind=GovernanceConfigKind(kind) if kind else None,
        )
        return GovernanceConfigListResponse(documents=tuple(document.model_dump(mode="json") for document in documents))

    async def get(self, document_id: UUID) -> GovernanceConfigResponse:
        document = await self._service.get(document_id)
        versions = await self._service.versions(document_id)
        latest = versions[-1] if versions else None
        return GovernanceConfigResponse(
            document=document.model_dump(mode="json"),
            latest_version=latest.model_dump(mode="json") if latest else None,
        )

    async def versions(self, document_id: UUID) -> GovernanceVersionListResponse:
        versions = await self._service.versions(document_id)
        return GovernanceVersionListResponse(versions=tuple(version.model_dump(mode="json") for version in versions))

    async def rollback(self, document_id: UUID, request: GovernanceRollbackApiRequest) -> GovernanceConfigResponse:
        document, version, reload_event = await self._service.rollback(
            document_id,
            GovernanceRollbackRequest(
                target_version=request.target_version,
                updated_by=request.updated_by,
                change_summary=request.change_summary,
            ),
        )
        return GovernanceConfigResponse(
            document=document.model_dump(mode="json"),
            latest_version=version.model_dump(mode="json"),
            reload_event=reload_event.model_dump(mode="json"),
        )

    async def reload_history(self) -> GovernanceReloadHistoryResponse:
        events = await self._service.reload_history()
        return GovernanceReloadHistoryResponse(events=tuple(event.model_dump(mode="json") for event in events))
