"""FastAPI adapter for Prompt Engineering Studio."""

from uuid import UUID

from app.schemas import (
    PromptComparisonResponse,
    PromptListResponse,
    PromptPreviewApiRequest,
    PromptPreviewResponse,
    PromptResponse,
    PromptRollbackApiRequest,
    PromptTestApiRequest,
    PromptTestResponse,
    PromptUpsertApiRequest,
    PromptVersionListResponse,
)
from core.contracts.prompt_studio import (
    PromptPreviewRequest,
    PromptRollbackRequest,
    PromptScope,
    PromptStatus,
    PromptTestRequest,
    PromptUpsert,
    PromptVariable,
)
from core.prompt_studio import PromptStudioService


class PromptStudioApplicationService:
    """API-facing Prompt Studio service."""

    def __init__(self, service: PromptStudioService | None = None) -> None:
        self._service = service or PromptStudioService()

    async def save(self, request: PromptUpsertApiRequest) -> PromptResponse:
        prompt, version = await self._service.save(
            PromptUpsert(
                name=request.name,
                scope=PromptScope(request.scope),
                agent_name=request.agent_name,
                markdown=request.markdown,
                variables=tuple(PromptVariable.model_validate(variable.model_dump()) for variable in request.variables),
                status=PromptStatus(request.status),
                updated_by=request.updated_by,
                change_summary=request.change_summary,
                metadata=request.metadata,
            )
        )
        return PromptResponse(prompt=prompt.model_dump(mode="json"), latest_version=version.model_dump(mode="json"))

    async def list(
        self,
        scope: str | None = None,
        agent_name: str | None = None,
        status: str | None = None,
    ) -> PromptListResponse:
        prompts = await self._service.list(
            scope=PromptScope(scope) if scope else None,
            agent_name=agent_name,
            status=PromptStatus(status) if status else None,
        )
        return PromptListResponse(prompts=tuple(prompt.model_dump(mode="json") for prompt in prompts))

    async def get(self, prompt_id: UUID) -> PromptResponse:
        prompt = await self._service.get(prompt_id)
        versions = await self._service.versions(prompt_id)
        latest = versions[-1] if versions else None
        return PromptResponse(
            prompt=prompt.model_dump(mode="json"),
            latest_version=latest.model_dump(mode="json") if latest else None,
        )

    async def versions(self, prompt_id: UUID) -> PromptVersionListResponse:
        versions = await self._service.versions(prompt_id)
        return PromptVersionListResponse(versions=tuple(version.model_dump(mode="json") for version in versions))

    async def rollback(self, prompt_id: UUID, request: PromptRollbackApiRequest) -> PromptResponse:
        prompt, version = await self._service.rollback(
            prompt_id,
            PromptRollbackRequest(
                target_version=request.target_version,
                updated_by=request.updated_by,
                change_summary=request.change_summary,
            ),
        )
        return PromptResponse(prompt=prompt.model_dump(mode="json"), latest_version=version.model_dump(mode="json"))

    async def preview(self, request: PromptPreviewApiRequest) -> PromptPreviewResponse:
        preview = await self._service.preview(
            PromptPreviewRequest(markdown=request.markdown, variables=request.variables)
        )
        return PromptPreviewResponse(preview=preview.model_dump(mode="json"))

    async def test(self, request: PromptTestApiRequest) -> PromptTestResponse:
        result = await self._service.test(
            PromptTestRequest(
                prompt_id=request.prompt_id,
                markdown=request.markdown,
                variables=request.variables,
                test_input=request.test_input,
                expected_output=request.expected_output,
                evaluator_notes=request.evaluator_notes,
            )
        )
        return PromptTestResponse(result=result.model_dump(mode="json"))

    async def compare(self, prompt_id: UUID, left_version: int, right_version: int) -> PromptComparisonResponse:
        comparison = await self._service.compare_versions(prompt_id, left_version, right_version)
        return PromptComparisonResponse(comparison=comparison.model_dump(mode="json"))
