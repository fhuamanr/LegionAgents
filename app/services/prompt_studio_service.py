"""FastAPI adapter for Prompt Engineering Studio."""

from pathlib import Path
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
        self._seeded = False

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
        await self._seed_defaults()
        prompts = await self._service.list(
            scope=PromptScope(scope) if scope else None,
            agent_name=agent_name,
            status=PromptStatus(status) if status else None,
        )
        return PromptListResponse(prompts=tuple(prompt.model_dump(mode="json") for prompt in prompts))

    async def get(self, prompt_id: UUID) -> PromptResponse:
        await self._seed_defaults()
        prompt = await self._service.get(prompt_id)
        versions = await self._service.versions(prompt_id)
        latest = versions[-1] if versions else None
        return PromptResponse(
            prompt=prompt.model_dump(mode="json"),
            latest_version=latest.model_dump(mode="json") if latest else None,
        )

    async def versions(self, prompt_id: UUID) -> PromptVersionListResponse:
        await self._seed_defaults()
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
        await self._seed_defaults()
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
        await self._seed_defaults()
        comparison = await self._service.compare_versions(prompt_id, left_version, right_version)
        return PromptComparisonResponse(comparison=comparison.model_dump(mode="json"))

    async def ensure_seeded(self) -> None:
        await self._seed_defaults()

    async def _seed_defaults(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        existing = await self._service.list()
        existing_names = {(prompt.scope.value, prompt.agent_name or "", prompt.name) for prompt in existing}
        root = Path.cwd()
        file_seeds: list[PromptUpsert] = []
        for path in sorted((root / "agents").glob("*/prompts/*.md")):
            agent_name = path.parts[-3]
            name = path.stem.replace("-", " ").replace("_", " ").title()
            file_seeds.append(
                PromptUpsert(
                    name=name,
                    scope=PromptScope.AGENT,
                    agent_name=agent_name,
                    markdown=path.read_text(encoding="utf-8"),
                    variables=tuple(),
                    status=PromptStatus.ACTIVE,
                    updated_by="seed",
                    change_summary="Seed agent prompt from repository.",
                    metadata={"source_path": str(path.resolve().relative_to(root)), "source_type": "seeded_file"},
                )
            )
        for path in sorted((root / "core" / "contracts").glob("*_prompt.md")):
            name = path.stem.replace("_", " ").title()
            file_seeds.append(
                PromptUpsert(
                    name=name,
                    scope=PromptScope.GLOBAL,
                    markdown=path.read_text(encoding="utf-8"),
                    variables=tuple(),
                    status=PromptStatus.ACTIVE,
                    updated_by="seed",
                    change_summary="Seed global prompt from repository.",
                    metadata={"source_path": str(path.resolve().relative_to(root)), "source_type": "seeded_file"},
                )
            )
        for seed in file_seeds:
            key = (seed.scope.value, seed.agent_name or "", seed.name)
            if key not in existing_names:
                await self._service.save(seed)
        if await self._service.list():
            return
        for agent_name, role in (
            ("ba", "business analyst"),
            ("architect", "software architect"),
            ("developer", "software developer"),
            ("qa", "quality engineer"),
            ("docs", "technical writer"),
            ("pr", "pull request coordinator"),
        ):
            await self._service.save(
                PromptUpsert(
                    name=f"{agent_name} runtime prompt",
                    scope=PromptScope.AGENT,
                    agent_name=agent_name,
                    markdown=(
                        f"You are the {role} agent.\n\n"
                        "Task: {{task}}\n\n"
                        "Use the runtime governance context, uploaded files, repository references, and upstream artifacts. "
                        "Return only the structured JSON required by this agent output contract."
                    ),
                    variables=(
                        PromptVariable(
                            name="task",
                            description="Current workflow task or workspace message.",
                            required=True,
                            default="Deliver the requested software change.",
                        ),
                    ),
                    status=PromptStatus.ACTIVE,
                    updated_by="seed",
                    change_summary="Seed editable MVP runtime prompt.",
                )
            )
