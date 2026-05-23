"""Persistence repository for Prompt Engineering Studio."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from core.contracts.prompt_studio import (
    PromptDocument,
    PromptRollbackRequest,
    PromptScope,
    PromptStatus,
    PromptUpsert,
    PromptVersion,
)
from core.persistence import PostgresJsonDocumentStore


class PromptRepository(ABC):
    """Prompt persistence boundary."""

    @abstractmethod
    async def upsert(self, request: PromptUpsert) -> tuple[PromptDocument, PromptVersion]:
        """Create or update a prompt."""

    @abstractmethod
    async def get(self, prompt_id: UUID) -> PromptDocument:
        """Get a prompt."""

    @abstractmethod
    async def list(
        self,
        scope: PromptScope | None = None,
        agent_name: str | None = None,
        status: PromptStatus | None = None,
    ) -> tuple[PromptDocument, ...]:
        """List prompts."""

    @abstractmethod
    async def versions(self, prompt_id: UUID) -> tuple[PromptVersion, ...]:
        """List prompt versions."""

    @abstractmethod
    async def rollback(self, prompt_id: UUID, request: PromptRollbackRequest) -> tuple[PromptDocument, PromptVersion]:
        """Rollback to a previous prompt version."""


class InMemoryPromptRepository(PromptRepository):
    """In-memory prompt persistence."""

    def __init__(self) -> None:
        self._documents: dict[UUID, PromptDocument] = {}
        self._versions: dict[UUID, list[PromptVersion]] = {}

    async def upsert(self, request: PromptUpsert) -> tuple[PromptDocument, PromptVersion]:
        existing = self._find_existing(request)
        now = datetime.now(timezone.utc)
        if existing is None:
            document = PromptDocument(
                name=request.name,
                scope=request.scope,
                agent_name=request.agent_name,
                markdown=request.markdown,
                variables=request.variables,
                status=request.status,
                updated_by=request.updated_by,
                created_at=now,
                updated_at=now,
                metadata=request.metadata,
            )
        else:
            document = existing.model_copy(
                update={
                    "name": request.name,
                    "markdown": request.markdown,
                    "variables": request.variables,
                    "status": request.status,
                    "version": existing.version + 1,
                    "updated_by": request.updated_by,
                    "updated_at": now,
                    "metadata": {**existing.metadata, **request.metadata},
                }
            )
        version = PromptVersion(
            prompt_id=document.id,
            version=document.version,
            markdown=document.markdown,
            variables=document.variables,
            changed_by=request.updated_by,
            change_summary=request.change_summary,
            metadata={"scope": document.scope.value, "agent_name": document.agent_name, "status": document.status.value},
        )
        self._documents[document.id] = document
        self._versions.setdefault(document.id, []).append(version)
        return document, version

    async def get(self, prompt_id: UUID) -> PromptDocument:
        return self._documents[prompt_id]

    async def list(
        self,
        scope: PromptScope | None = None,
        agent_name: str | None = None,
        status: PromptStatus | None = None,
    ) -> tuple[PromptDocument, ...]:
        documents = tuple(sorted(self._documents.values(), key=lambda item: (item.scope.value, item.agent_name or "", item.name)))
        return tuple(
            document
            for document in documents
            if (scope is None or document.scope == scope)
            and (agent_name is None or document.agent_name == agent_name)
            and (status is None or document.status == status)
        )

    async def versions(self, prompt_id: UUID) -> tuple[PromptVersion, ...]:
        return tuple(self._versions.get(prompt_id, tuple()))

    async def rollback(self, prompt_id: UUID, request: PromptRollbackRequest) -> tuple[PromptDocument, PromptVersion]:
        document = await self.get(prompt_id)
        versions = await self.versions(prompt_id)
        target = next(version for version in versions if version.version == request.target_version)
        return await self.upsert(
            PromptUpsert(
                name=document.name,
                scope=document.scope,
                agent_name=document.agent_name,
                markdown=target.markdown,
                variables=target.variables,
                status=document.status,
                updated_by=request.updated_by,
                change_summary=request.change_summary or f"Rollback to version {request.target_version}",
                metadata={**document.metadata, "rollback_to_version": request.target_version},
            )
        )

    def _find_existing(self, request: PromptUpsert) -> PromptDocument | None:
        for document in self._documents.values():
            if document.scope == request.scope and document.agent_name == request.agent_name and document.name == request.name:
                return document
        return None


class PostgresPromptRepository(PromptRepository):
    """PostgreSQL-backed prompt persistence with version history."""

    _documents_bucket = "prompt_documents"
    _versions_bucket = "prompt_versions"

    def __init__(self, store: PostgresJsonDocumentStore) -> None:
        self._store = store

    async def upsert(self, request: PromptUpsert) -> tuple[PromptDocument, PromptVersion]:
        existing = self._find_existing(await self.list(), request)
        now = datetime.now(timezone.utc)
        if existing is None:
            document = PromptDocument(
                name=request.name,
                scope=request.scope,
                agent_name=request.agent_name,
                markdown=request.markdown,
                variables=request.variables,
                status=request.status,
                updated_by=request.updated_by,
                created_at=now,
                updated_at=now,
                metadata=request.metadata,
            )
        else:
            document = existing.model_copy(
                update={
                    "name": request.name,
                    "markdown": request.markdown,
                    "variables": request.variables,
                    "status": request.status,
                    "version": existing.version + 1,
                    "updated_by": request.updated_by,
                    "updated_at": now,
                    "metadata": {**existing.metadata, **request.metadata},
                }
            )
        version = PromptVersion(
            prompt_id=document.id,
            version=document.version,
            markdown=document.markdown,
            variables=document.variables,
            changed_by=request.updated_by,
            change_summary=request.change_summary,
            metadata={"scope": document.scope.value, "agent_name": document.agent_name, "status": document.status.value},
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

    async def get(self, prompt_id: UUID) -> PromptDocument:
        return PromptDocument.model_validate(
            await self._store.get(bucket=self._documents_bucket, document_id=prompt_id)
        )

    async def list(
        self,
        scope: PromptScope | None = None,
        agent_name: str | None = None,
        status: PromptStatus | None = None,
    ) -> tuple[PromptDocument, ...]:
        documents = tuple(
            PromptDocument.model_validate(item)
            for item in await self._store.list(bucket=self._documents_bucket)
        )
        return tuple(
            document
            for document in documents
            if (scope is None or document.scope == scope)
            and (agent_name is None or document.agent_name == agent_name)
            and (status is None or document.status == status)
        )

    async def versions(self, prompt_id: UUID) -> tuple[PromptVersion, ...]:
        versions = tuple(
            PromptVersion.model_validate(item)
            for item in await self._store.list(
                bucket=self._versions_bucket,
                key_prefix=f"{prompt_id}:",
            )
        )
        return tuple(sorted(versions, key=lambda item: item.version))

    async def rollback(self, prompt_id: UUID, request: PromptRollbackRequest) -> tuple[PromptDocument, PromptVersion]:
        document = await self.get(prompt_id)
        versions = await self.versions(prompt_id)
        target = next(version for version in versions if version.version == request.target_version)
        return await self.upsert(
            PromptUpsert(
                name=document.name,
                scope=document.scope,
                agent_name=document.agent_name,
                markdown=target.markdown,
                variables=target.variables,
                status=document.status,
                updated_by=request.updated_by,
                change_summary=request.change_summary or f"Rollback to version {request.target_version}",
                metadata={**document.metadata, "rollback_to_version": request.target_version},
            )
        )

    def _find_existing(
        self,
        documents: tuple[PromptDocument, ...],
        request: PromptUpsert,
    ) -> PromptDocument | None:
        for document in documents:
            if document.scope == request.scope and document.agent_name == request.agent_name and document.name == request.name:
                return document
        return None

    def _document_key(self, document: PromptDocument) -> str:
        return f"{document.scope.value}:{document.agent_name or '*'}:{document.name}"
