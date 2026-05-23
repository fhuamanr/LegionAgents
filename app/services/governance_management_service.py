"""Governance management application service."""

from __future__ import annotations

import logging
from pathlib import Path
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

logger = logging.getLogger(__name__)


class GovernanceManagementApplicationService:
    """FastAPI adapter for dynamic governance management."""

    _SEED_PATHS = (
        "agents",
        "core/governance",
        "core/prompts",
        "repository/standards",
    )

    def __init__(self, service: GovernanceManagementService | None = None) -> None:
        self._service = service or GovernanceManagementService()
        self._seeded = False

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
        await self._seed_defaults()
        documents = await self._service.list(
            scope=GovernanceConfigScope(scope) if scope else None,
            agent_name=agent_name,
            kind=GovernanceConfigKind(kind) if kind else None,
        )
        return GovernanceConfigListResponse(documents=tuple(document.model_dump(mode="json") for document in documents))

    async def get(self, document_id: UUID) -> GovernanceConfigResponse:
        await self._seed_defaults()
        document = await self._service.get(document_id)
        versions = await self._service.versions(document_id)
        latest = versions[-1] if versions else None
        return GovernanceConfigResponse(
            document=document.model_dump(mode="json"),
            latest_version=latest.model_dump(mode="json") if latest else None,
        )

    async def versions(self, document_id: UUID) -> GovernanceVersionListResponse:
        await self._seed_defaults()
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

    async def delete(self, document_id: UUID) -> None:
        document = await self._service.get(document_id)
        if document.protected:
            raise ValueError("Protected seeded documents cannot be deleted.")
        await self._service.delete(document_id)

    async def ensure_seeded(self) -> None:
        await self._seed_defaults()

    async def _seed_defaults(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        root = Path.cwd()
        existing = await self._service.list()
        existing_keys = {
            (
                document.scope.value,
                document.agent_name or "",
                document.kind.value,
                document.metadata.get("source_path") or "",
            )
            for document in existing
        }

        seeds: list[GovernanceConfigUpsert] = []
        scanned = 0
        for relative in self._SEED_PATHS:
            seed_root = (root / relative).resolve()
            if not seed_root.exists():
                continue
            for path in seed_root.rglob("*.md"):
                scanned += 1
                seed = self._seed_for_path(path, root)
                key = (seed.scope.value, seed.agent_name or "", seed.kind.value, seed.metadata["source_path"])
                if key in existing_keys:
                    continue
                seeds.append(seed)

        for seed in seeds:
            await self._service.save(seed)

        logger.info(
            "governance seed complete: scanned=%s created=%s existing=%s",
            scanned,
            len(seeds),
            len(existing_keys),
        )

    def _seed_for_path(self, path: Path, root: Path) -> GovernanceConfigUpsert:
        relative = path.resolve().relative_to(root).as_posix()
        path_parts = relative.split("/")
        scope = GovernanceConfigScope.GLOBAL
        agent_name: str | None = None
        if len(path_parts) > 1 and path_parts[0] == "agents":
            scope = GovernanceConfigScope.AGENT
            agent_name = path_parts[1]

        stem = path.stem.lower()
        kind = self._infer_kind(relative, stem)
        title = stem.replace("-", " ").replace("_", " ").title()
        prefix = f"{agent_name} " if agent_name else "Global "
        return GovernanceConfigUpsert(
            scope=scope,
            kind=kind,
            name=f"{prefix}{title}",
            markdown=path.read_text(encoding="utf-8"),
            agent_name=agent_name,
            updated_by="seed",
            change_summary="Initial markdown seed from repository.",
            metadata={
                "source_path": relative,
                "source_type": "seeded_file",
                "is_active": True,
                "protected": True,
            },
        )

    def _infer_kind(self, relative: str, stem: str) -> GovernanceConfigKind:
        if "prompt" in relative or "prompt" in stem:
            return GovernanceConfigKind.PROMPT
        if "anti-gravity" in stem or "anti_gravity" in stem:
            return GovernanceConfigKind.ANTI_GRAVITY
        if "gravity" in stem:
            return GovernanceConfigKind.GRAVITY
        if "personality" in stem:
            return GovernanceConfigKind.PERSONALITY
        if "architecture" in stem:
            return GovernanceConfigKind.ARCHITECTURE
        if "coding" in stem or "guideline" in stem or "standards" in stem:
            return GovernanceConfigKind.CODING_STANDARDS
        if "severity" in stem:
            return GovernanceConfigKind.SEVERITY_RULES
        if "forbidden" in stem:
            return GovernanceConfigKind.FORBIDDEN_RULES
        if "naming" in stem:
            return GovernanceConfigKind.NAMING_RULES
        if "testing" in stem or "test-strategy" in stem:
            return GovernanceConfigKind.TESTING_RULES
        if "security" in stem:
            return GovernanceConfigKind.SECURITY_RULES
        if "qa" in stem:
            return GovernanceConfigKind.QA_POLICY
        if "documentation" in stem or "docs" in stem:
            return GovernanceConfigKind.DOCUMENTATION_RULES
        if "workflow" in stem:
            return GovernanceConfigKind.WORKFLOW_RULES
        if stem == "pr" or "pull-request" in stem:
            return GovernanceConfigKind.PR_RULES
        return GovernanceConfigKind.OTHER
