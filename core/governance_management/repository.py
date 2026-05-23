"""Persistence repositories for dynamic governance documents."""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from core.contracts.governance_management import (
    GovernanceConfigDocument,
    GovernanceConfigKind,
    GovernanceConfigScope,
    GovernanceConfigUpsert,
    GovernanceConfigVersion,
)
from core.persistence import PostgresJsonDocumentStore


class GovernanceConfigRepository(ABC):
    """Persistence boundary for governance configuration."""

    @abstractmethod
    async def upsert(self, request: GovernanceConfigUpsert) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        """Create or update a governance document."""

    @abstractmethod
    async def get(self, document_id: UUID) -> GovernanceConfigDocument:
        """Get a document by id."""

    @abstractmethod
    async def list(
        self,
        scope: GovernanceConfigScope | None = None,
        agent_name: str | None = None,
        kind: GovernanceConfigKind | None = None,
    ) -> tuple[GovernanceConfigDocument, ...]:
        """List documents."""

    @abstractmethod
    async def versions(self, document_id: UUID) -> tuple[GovernanceConfigVersion, ...]:
        """List document versions."""

    @abstractmethod
    async def restore_version(
        self,
        document_id: UUID,
        target_version: int,
        updated_by: str,
        change_summary: str | None,
    ) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        """Restore a historical version."""

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        """Delete a document."""


class InMemoryGovernanceConfigRepository(GovernanceConfigRepository):
    """In-memory governance config persistence."""

    def __init__(self) -> None:
        self._documents: dict[UUID, GovernanceConfigDocument] = {}
        self._versions: dict[UUID, list[GovernanceConfigVersion]] = {}

    async def upsert(self, request: GovernanceConfigUpsert) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        existing = self._find_existing(request)
        now = datetime.now(timezone.utc)
        if existing is None:
            document = GovernanceConfigDocument(
                scope=request.scope,
                kind=request.kind,
                name=request.name,
                markdown=request.markdown,
                agent_name=request.agent_name,
                updated_by=request.updated_by,
                metadata=request.metadata,
                created_at=now,
                updated_at=now,
            )
        else:
            document = existing.model_copy(
                update={
                    "name": request.name,
                    "markdown": request.markdown,
                    "version": existing.version + 1,
                    "updated_by": request.updated_by,
                    "updated_at": now,
                    "metadata": {**existing.metadata, **request.metadata},
                }
            )
        version = GovernanceConfigVersion(
            document_id=document.id,
            version=document.version,
            markdown=document.markdown,
            changed_by=request.updated_by,
            change_summary=request.change_summary,
            metadata={"kind": document.kind.value, "scope": document.scope.value, "agent_name": document.agent_name},
        )
        self._documents[document.id] = document
        self._versions.setdefault(document.id, []).append(version)
        return document, version

    async def get(self, document_id: UUID) -> GovernanceConfigDocument:
        return self._documents[document_id]

    async def list(
        self,
        scope: GovernanceConfigScope | None = None,
        agent_name: str | None = None,
        kind: GovernanceConfigKind | None = None,
    ) -> tuple[GovernanceConfigDocument, ...]:
        documents = tuple(sorted(self._documents.values(), key=lambda item: (item.scope.value, item.agent_name or "", item.kind.value)))
        return tuple(
            document
            for document in documents
            if (scope is None or document.scope == scope)
            and (agent_name is None or document.agent_name == agent_name)
            and (kind is None or document.kind == kind)
        )

    async def versions(self, document_id: UUID) -> tuple[GovernanceConfigVersion, ...]:
        return tuple(self._versions.get(document_id, tuple()))

    async def restore_version(
        self,
        document_id: UUID,
        target_version: int,
        updated_by: str,
        change_summary: str | None,
    ) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        document = await self.get(document_id)
        versions = await self.versions(document_id)
        target = next(version for version in versions if version.version == target_version)
        request = GovernanceConfigUpsert(
            scope=document.scope,
            kind=document.kind,
            name=document.name,
            markdown=target.markdown,
            agent_name=document.agent_name,
            updated_by=updated_by,
            change_summary=change_summary or f"Rollback to version {target_version}",
            metadata={**document.metadata, "rollback_from_version": document.version, "rollback_to_version": target_version},
        )
        return await self.upsert(request)

    async def delete(self, document_id: UUID) -> None:
        self._documents.pop(document_id, None)
        self._versions.pop(document_id, None)

    def _find_existing(self, request: GovernanceConfigUpsert) -> GovernanceConfigDocument | None:
        for document in self._documents.values():
            if document.scope == request.scope and document.kind == request.kind and document.agent_name == request.agent_name:
                return document
        return None


class FileGovernanceConfigRepository(InMemoryGovernanceConfigRepository):
    """JSON-file-backed governance persistence for live local management."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._storage_path = (storage_path or Path.cwd() / "outputs" / "governance" / "configs.json").resolve()
        super().__init__()
        self._load()

    async def upsert(self, request: GovernanceConfigUpsert) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        result = await super().upsert(request)
        self._persist()
        return result

    async def restore_version(
        self,
        document_id: UUID,
        target_version: int,
        updated_by: str,
        change_summary: str | None,
    ) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        result = await super().restore_version(document_id, target_version, updated_by, change_summary)
        self._persist()
        return result

    async def delete(self, document_id: UUID) -> None:
        await super().delete(document_id)
        self._persist()

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._documents = {
            UUID(item["id"]): GovernanceConfigDocument.model_validate(item)
            for item in payload.get("documents", [])
        }
        self._versions = {}
        for item in payload.get("versions", []):
            version = GovernanceConfigVersion.model_validate(item)
            self._versions.setdefault(version.document_id, []).append(version)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "documents": [document.model_dump(mode="json") for document in self._documents.values()],
            "versions": [
                version.model_dump(mode="json")
                for versions in self._versions.values()
                for version in versions
            ],
        }
        self._storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class PostgresGovernanceConfigRepository(GovernanceConfigRepository):
    """PostgreSQL-backed editable governance persistence."""

    _documents_bucket = "governance_documents"
    _versions_bucket = "governance_versions"

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store

    async def upsert(self, request: GovernanceConfigUpsert) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        existing = self._find_existing(await self.list(), request)
        now = datetime.now(timezone.utc)
        if existing is None:
            document = GovernanceConfigDocument(
                scope=request.scope,
                kind=request.kind,
                name=request.name,
                markdown=request.markdown,
                agent_name=request.agent_name,
                updated_by=request.updated_by,
                source_path=Path(str(request.metadata.get("source_path"))) if request.metadata.get("source_path") else None,
                source_type=str(request.metadata.get("source_type") or "runtime_created"),
                is_active=bool(request.metadata.get("is_active", True)),
                protected=bool(request.metadata.get("protected", False)),
                metadata=request.metadata,
                created_at=now,
                updated_at=now,
            )
        else:
            document = existing.model_copy(
                update={
                    "name": request.name,
                    "markdown": request.markdown,
                    "version": existing.version + 1,
                    "updated_by": request.updated_by,
                    "updated_at": now,
                    "metadata": {**existing.metadata, **request.metadata},
                }
            )
        version = GovernanceConfigVersion(
            document_id=document.id,
            version=document.version,
            markdown=document.markdown,
            changed_by=request.updated_by,
            change_summary=request.change_summary,
            metadata={"kind": document.kind.value, "scope": document.scope.value, "agent_name": document.agent_name},
        )
        await self._store.upsert(
            bucket=self._documents_bucket,
            document_id=document.id,
            key=self._document_key(document),
            payload=document.model_dump(mode="json"),
        )
        await self._store.upsert(
            bucket=self._versions_bucket,
            document_id=version.id,
            key=f"{document.id}:{version.version:08d}",
            payload=version.model_dump(mode="json"),
        )
        return document, version

    async def get(self, document_id: UUID) -> GovernanceConfigDocument:
        return GovernanceConfigDocument.model_validate(
            await self._store.get(bucket=self._documents_bucket, document_id=document_id)
        )

    async def list(
        self,
        scope: GovernanceConfigScope | None = None,
        agent_name: str | None = None,
        kind: GovernanceConfigKind | None = None,
    ) -> tuple[GovernanceConfigDocument, ...]:
        documents = tuple(
            GovernanceConfigDocument.model_validate(item)
            for item in await self._store.list(bucket=self._documents_bucket)
        )
        return tuple(
            document
            for document in documents
            if (scope is None or document.scope == scope)
            and (agent_name is None or document.agent_name == agent_name)
            and (kind is None or document.kind == kind)
        )

    async def versions(self, document_id: UUID) -> tuple[GovernanceConfigVersion, ...]:
        versions = tuple(
            GovernanceConfigVersion.model_validate(item)
            for item in await self._store.list(
                bucket=self._versions_bucket,
                key_prefix=f"{document_id}:",
            )
        )
        return tuple(sorted(versions, key=lambda item: item.version))

    async def restore_version(
        self,
        document_id: UUID,
        target_version: int,
        updated_by: str,
        change_summary: str | None,
    ) -> tuple[GovernanceConfigDocument, GovernanceConfigVersion]:
        document = await self.get(document_id)
        versions = await self.versions(document_id)
        target = next(version for version in versions if version.version == target_version)
        return await self.upsert(
            GovernanceConfigUpsert(
                scope=document.scope,
                kind=document.kind,
                name=document.name,
                markdown=target.markdown,
                agent_name=document.agent_name,
                updated_by=updated_by,
                change_summary=change_summary or f"Rollback to version {target_version}",
                metadata={**document.metadata, "rollback_from_version": document.version, "rollback_to_version": target_version},
            )
        )

    async def delete(self, document_id: UUID) -> None:
        await self._store.delete(bucket=self._documents_bucket, document_id=document_id)

    def _find_existing(
        self,
        documents: tuple[GovernanceConfigDocument, ...],
        request: GovernanceConfigUpsert,
    ) -> GovernanceConfigDocument | None:
        for document in documents:
            if document.scope == request.scope and document.kind == request.kind and document.agent_name == request.agent_name:
                return document
        return None

    def _document_key(self, document: GovernanceConfigDocument) -> str:
        return f"{document.scope.value}:{document.agent_name or '*'}:{document.kind.value}"
