"""Runtime context assembly."""

from abc import ABC, abstractmethod
import os
from pathlib import Path

from core.context import FileSystemAgentContextLoader
from core.context_engineering.engine import ContextEngineeringEngine
from core.context_engineering.models import ContextEngineeringConfig, ContextEngineeringRequest
from core.contracts.artifacts import ArtifactKind
from core.contracts.context import AgentContext, ContextDocument, ContextPriority, ContextSection, ContextSectionName
from core.contracts.execution import AgentExecutionRequest
from core.contracts.prompt_studio import PromptScope, PromptStatus
from core.governance import AgentGovernanceEngine
from core.persistence import PostgresJsonDocumentStore
from core.prompt_studio import PostgresPromptRepository
from core.runtime.models import RuntimeAgentConfig


class ContextAssembler(ABC):
    """Assembles isolated runtime context for an agent."""

    @abstractmethod
    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        """Build an isolated context package for the request."""


class MarkdownRuleContextAssembler(ContextAssembler):
    """Builds budgeted markdown, repository, memory, and upstream context."""

    def __init__(
        self,
        context_loader: FileSystemAgentContextLoader | None = None,
        context_engineering_engine: ContextEngineeringEngine | None = None,
    ) -> None:
        self._context_loader = context_loader or FileSystemAgentContextLoader()
        self._context_engineering_engine = context_engineering_engine or ContextEngineeringEngine(
            context_loader=self._context_loader,
        )

    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        engineered = await self._context_engineering_engine.build(
            ContextEngineeringRequest(
                agent_name=config.name,
                task=request.task,
                agent_context_path=config.context_path,
                repository_path=self._repository_path(request, config),
                architecture_context=self._architecture_context(request),
                upstream_context=self._upstream_context(request),
                workflow_id=request.workflow_id,
                thread_id=str(request.metadata.get("thread_id", "")) or None,
                config=self._config_from_runtime(config),
            )
        )
        context = await self._append_runtime_prompts(engineered.context, config)
        return context.model_copy(
            update={
                "metadata": {
                    **context.metadata,
                    "context_warnings": engineered.warnings,
                    "requested_agent": request.agent_name,
                    "context_engineering": {
                        **engineered.metadata,
                        "engineered": True,
                        "selected_items": tuple(item.id for item in engineered.selected_items),
                        "dropped_items": tuple(item.id for item in engineered.dropped_items),
                        "token_hint": engineered.token_hint,
                        "warnings": engineered.warnings,
                    },
                }
            }
        )

    def _config_from_runtime(self, config: RuntimeAgentConfig) -> ContextEngineeringConfig:
        compact_mode = bool(config.metadata.get("compact_mode", False))
        return ContextEngineeringConfig(
            max_token_hint=config.max_context_token_hint or (3_000 if compact_mode else 12_000),
            reserved_output_token_hint=int(config.metadata.get("reserved_output_token_hint", 800 if compact_mode else 1_500)),
            enable_repository_summary=bool(config.metadata.get("enable_repository_summary", True)),
            enable_architecture_summary=bool(config.metadata.get("enable_architecture_summary", True)),
            enable_memory=bool(config.metadata.get("enable_memory", True)),
            enable_compression=bool(config.metadata.get("enable_compression", True)),
            selected_repository_file_limit=int(config.metadata.get("selected_repository_file_limit", 4 if compact_mode else 12)),
            repository_file_limit=int(config.metadata.get("repository_file_limit", 24 if compact_mode else 200)),
            repository_file_token_soft_limit=int(config.metadata.get("repository_file_token_soft_limit", 450 if compact_mode else 900)),
            repository_file_max_bytes=int(config.metadata.get("repository_file_max_bytes", 8_000 if compact_mode else 20_000)),
            item_token_soft_limit=int(config.metadata.get("item_token_soft_limit", 350 if compact_mode else 700)),
        )

    def _repository_path(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> Path | None:
        configured = (
            request.metadata.get("repository_path")
            or request.metadata.get("workspace_path")
            or config.metadata.get("repository_path")
        )
        if configured:
            return Path(str(configured))
        try:
            return config.context_path.parents[1]
        except IndexError:
            return None

    def _architecture_context(self, request: AgentExecutionRequest) -> str | None:
        direct = str(request.metadata.get("architecture_context", "")).strip()
        if direct:
            return direct
        architecture_artifacts = [
            artifact
            for artifact in request.upstream_artifacts
            if artifact.kind == ArtifactKind.ARCHITECTURE and artifact.content
        ]
        return "\n\n".join(str(artifact.content) for artifact in architecture_artifacts) or None

    def _upstream_context(self, request: AgentExecutionRequest) -> tuple[str, ...]:
        values: list[str] = []
        for key in ("ba_stories", "architecture_context", "qa_results", "generated_outputs"):
            value = str(request.metadata.get(key, "")).strip()
            if value:
                values.append(value)
        for artifact in request.upstream_artifacts:
            if artifact.content:
                values.append(
                    f"{artifact.kind.value} artifact from {artifact.producer_agent}: {artifact.name}\n"
                    f"{artifact.content}"
                )
            else:
                values.append(f"{artifact.kind.value} artifact from {artifact.producer_agent}: {artifact.name}")
        return tuple(values)

    async def _append_runtime_prompts(
        self,
        context: AgentContext,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        repository = self._runtime_prompt_repository()
        if repository is None:
            return context
        prompts = tuple(await repository.list(scope=PromptScope.GLOBAL, status=PromptStatus.ACTIVE)) + tuple(
            await repository.list(scope=PromptScope.AGENT, agent_name=config.name, status=PromptStatus.ACTIVE)
        )
        documents = tuple(
            ContextDocument(
                name=f"Runtime Prompt: {prompt.name}",
                path=Path(f"runtime/prompts/{prompt.id}.md"),
                content=prompt.markdown,
                section=ContextSectionName.PROMPTS,
                priority=ContextPriority.HIGH,
                token_hint=max(1, len(prompt.markdown) // 4),
                metadata={
                    "prompt_id": str(prompt.id),
                    "prompt_version": prompt.version,
                    "scope": prompt.scope.value,
                    "agent_name": prompt.agent_name,
                    "runtime_editable": True,
                },
            )
            for prompt in prompts
            if prompt.markdown.strip()
        )
        if not documents:
            return context
        sections = list(context.sections)
        prompt_index = next(
            (index for index, section in enumerate(sections) if section.name == ContextSectionName.PROMPTS),
            None,
        )
        if prompt_index is None:
            sections.append(
                ContextSection(
                    name=ContextSectionName.PROMPTS,
                    documents=documents,
                    priority=ContextPriority.HIGH,
                )
            )
        else:
            section = sections[prompt_index]
            sections[prompt_index] = section.model_copy(
                update={"documents": section.documents + documents, "priority": ContextPriority.HIGH}
            )
        return context.model_copy(
            update={
                "sections": tuple(sections),
                "metadata": {
                    **context.metadata,
                    "runtime_prompt_count": len(documents),
                    "document_count": int(context.metadata.get("document_count", 0)) + len(documents),
                },
            }
        )

    def _runtime_prompt_repository(self) -> PostgresPromptRepository | None:
        dsn = os.getenv("POSTGRES_DSN", "").strip()
        if not dsn:
            return None
        return PostgresPromptRepository(PostgresJsonDocumentStore(dsn))


class GovernanceRuntimeContextAssembler(MarkdownRuleContextAssembler):
    """Builds dynamic engineered context plus inherited governance policy metadata."""

    def __init__(
        self,
        context_loader: FileSystemAgentContextLoader | None = None,
        context_engineering_engine: ContextEngineeringEngine | None = None,
        governance_engine: AgentGovernanceEngine | None = None,
        agents_root: Path | None = None,
        standards_root: Path | None = None,
    ) -> None:
        super().__init__(
            context_loader=context_loader,
            context_engineering_engine=context_engineering_engine,
        )
        self._governance_engine = governance_engine
        self._agents_root = agents_root
        self._standards_root = standards_root

    async def assemble(
        self,
        request: AgentExecutionRequest,
        config: RuntimeAgentConfig,
    ) -> AgentContext:
        context = await super().assemble(request, config)
        engine = self._governance_engine or self._build_engine(config.context_path)
        policy = await engine.effective_policy_for_agent(config.name)
        governance_text = "\n".join(
            f"- [{rule.priority.value}/{rule.effect.value}/{rule.category.value}] {rule.description}"
            for rule in policy.rules
        )
        return context.model_copy(
            update={
                "metadata": {
                    **context.metadata,
                    "governance_policy_name": policy.name,
                    "governance_rule_count": len(policy.rules),
                    "governance_rules": tuple(rule.model_dump(mode="json") for rule in policy.rules),
                    "governance_text": governance_text,
                }
            }
        )

    def _build_engine(self, context_path: Path) -> AgentGovernanceEngine:
        agents_root = self._agents_root or context_path.parent
        standards_root = self._standards_root or agents_root.parent / "repository" / "standards"
        return AgentGovernanceEngine(agents_root=agents_root, standards_root=standards_root)
