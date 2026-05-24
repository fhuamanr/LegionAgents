"""Application dependency container."""

from functools import lru_cache
import os

from app.services.execution_service import ExecutionService
from app.services.approval_service import ApprovalApplicationService
from app.services.observability_service import ObservabilityApplicationService
from app.services.governance_management_service import GovernanceManagementApplicationService
from app.services.chat_service import WorkspaceChatApplicationService
from app.services.prompt_studio_service import PromptStudioApplicationService
from app.services.provider_service import ProviderApplicationService
from app.services.workspace_management_service import WorkspaceManagementApplicationService
from app.services.security_service import SecurityApplicationService
from core.agents.providers import ProviderRegistry, RoutingModelClient
from core.graph import PostgresWorkflowExecutionRepository
from core.governance_management import GovernanceManagementService, PostgresGovernanceConfigRepository
from core.persistence import PostgresJsonDocumentStore
from core.prompt_studio import PostgresPromptRepository, PromptStudioService
from core.chat import PostgresChatConversationRepository, WorkspaceChatService
from core.streaming import PostgresBackedExecutionEventBus
from core.workspaces import PostgresWorkspaceRepository, WorkspaceManagementService


class AppContainer:
    """Application service container."""

    def __init__(self) -> None:
        postgres_store = self._postgres_store()
        workflow_repository = (
            PostgresWorkflowExecutionRepository(postgres_store)
            if postgres_store is not None
            else None
        )
        governance_repository = (
            PostgresGovernanceConfigRepository(postgres_store)
            if postgres_store is not None
            else None
        )
        prompt_repository = (
            PostgresPromptRepository(postgres_store)
            if postgres_store is not None
            else None
        )
        workspace_repository = (
            PostgresWorkspaceRepository(postgres_store)
            if postgres_store is not None
            else None
        )
        chat_repository = (
            PostgresChatConversationRepository(postgres_store)
            if postgres_store is not None
            else None
        )
        self.provider_registry = ProviderRegistry(postgres_store)
        self.provider_service = ProviderApplicationService(self.provider_registry)
        execution_event_bus = PostgresBackedExecutionEventBus(postgres_store) if postgres_store is not None else None
        self.execution_service = ExecutionService(
            event_bus=execution_event_bus,
            model_client=RoutingModelClient(self.provider_registry),
            workflow_repository=workflow_repository,
            state_store=postgres_store,
        )
        self.approval_service = ApprovalApplicationService(self.execution_service)
        self.observability_service = ObservabilityApplicationService(self.execution_service)
        self.governance_management_service = GovernanceManagementApplicationService(
            GovernanceManagementService(repository=governance_repository)
            if governance_repository is not None
            else None
        )
        self.chat_service = WorkspaceChatApplicationService(
            self.execution_service,
            chat_service=WorkspaceChatService(repository=chat_repository) if chat_repository is not None else None,
        )
        self.prompt_studio_service = PromptStudioApplicationService(
            PromptStudioService(repository=prompt_repository)
            if prompt_repository is not None
            else None
        )
        self.workspace_management_service = WorkspaceManagementApplicationService(
            WorkspaceManagementService(repository=workspace_repository)
            if workspace_repository is not None
            else None
        )
        self.security_service = SecurityApplicationService()

    def _postgres_store(self) -> PostgresJsonDocumentStore | None:
        dsn = os.getenv("POSTGRES_DSN", "").strip()
        if not dsn:
            return None
        return PostgresJsonDocumentStore(dsn)


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()


def get_execution_service() -> ExecutionService:
    return get_container().execution_service


def get_approval_service() -> ApprovalApplicationService:
    return get_container().approval_service


def get_observability_service() -> ObservabilityApplicationService:
    return get_container().observability_service


def get_governance_management_service() -> GovernanceManagementApplicationService:
    return get_container().governance_management_service


def get_chat_service() -> WorkspaceChatApplicationService:
    return get_container().chat_service


def get_prompt_studio_service() -> PromptStudioApplicationService:
    return get_container().prompt_studio_service


def get_provider_service() -> ProviderApplicationService:
    return get_container().provider_service


def get_workspace_management_service() -> WorkspaceManagementApplicationService:
    return get_container().workspace_management_service


def get_security_service() -> SecurityApplicationService:
    return get_container().security_service
