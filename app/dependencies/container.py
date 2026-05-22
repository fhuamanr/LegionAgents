"""Application dependency container."""

from functools import lru_cache

from app.services.execution_service import ExecutionService
from app.services.approval_service import ApprovalApplicationService
from app.services.observability_service import ObservabilityApplicationService
from app.services.governance_management_service import GovernanceManagementApplicationService
from app.services.chat_service import WorkspaceChatApplicationService
from app.services.prompt_studio_service import PromptStudioApplicationService


class AppContainer:
    """Application service container."""

    def __init__(self) -> None:
        self.execution_service = ExecutionService()
        self.approval_service = ApprovalApplicationService(self.execution_service)
        self.observability_service = ObservabilityApplicationService(self.execution_service)
        self.governance_management_service = GovernanceManagementApplicationService()
        self.chat_service = WorkspaceChatApplicationService(self.execution_service)
        self.prompt_studio_service = PromptStudioApplicationService()


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
