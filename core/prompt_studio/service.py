"""Prompt Studio application service."""

from uuid import UUID

from core.contracts.prompt_studio import (
    PromptComparisonResult,
    PromptDocument,
    PromptPreview,
    PromptPreviewRequest,
    PromptRollbackRequest,
    PromptScope,
    PromptStatus,
    PromptTestRequest,
    PromptTestResult,
    PromptUpsert,
    PromptVersion,
)
from core.prompt_studio.engine import PromptStudioEngine
from core.prompt_studio.repository import InMemoryPromptRepository, PromptRepository


class PromptStudioService:
    """Coordinates prompt editing, testing, versioning, comparison, and rollback."""

    def __init__(
        self,
        repository: PromptRepository | None = None,
        engine: PromptStudioEngine | None = None,
    ) -> None:
        self._repository = repository or InMemoryPromptRepository()
        self._engine = engine or PromptStudioEngine()

    async def save(self, request: PromptUpsert) -> tuple[PromptDocument, PromptVersion]:
        return await self._repository.upsert(request)

    async def list(
        self,
        scope: PromptScope | None = None,
        agent_name: str | None = None,
        status: PromptStatus | None = None,
    ) -> tuple[PromptDocument, ...]:
        return await self._repository.list(scope=scope, agent_name=agent_name, status=status)

    async def get(self, prompt_id: UUID) -> PromptDocument:
        return await self._repository.get(prompt_id)

    async def versions(self, prompt_id: UUID) -> tuple[PromptVersion, ...]:
        return await self._repository.versions(prompt_id)

    async def rollback(self, prompt_id: UUID, request: PromptRollbackRequest) -> tuple[PromptDocument, PromptVersion]:
        return await self._repository.rollback(prompt_id, request)

    async def preview(self, request: PromptPreviewRequest) -> PromptPreview:
        return await self._engine.preview(request)

    async def test(self, request: PromptTestRequest) -> PromptTestResult:
        markdown = request.markdown
        if markdown is None and request.prompt_id is not None:
            markdown = (await self.get(request.prompt_id)).markdown
        if markdown is None:
            raise ValueError("prompt_id or markdown is required for prompt testing")
        return await self._engine.test(request, markdown)

    async def compare_versions(
        self,
        prompt_id: UUID,
        left_version: int,
        right_version: int,
    ) -> PromptComparisonResult:
        versions = await self.versions(prompt_id)
        left = next(version for version in versions if version.version == left_version)
        right = next(version for version in versions if version.version == right_version)
        return await self._engine.compare(left.markdown, right.markdown, left.version, right.version)
