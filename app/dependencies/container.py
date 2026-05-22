"""Application dependency container."""

from functools import lru_cache

from app.services.execution_service import ExecutionService
from app.services.approval_service import ApprovalApplicationService


class AppContainer:
    """Application service container."""

    def __init__(self) -> None:
        self.execution_service = ExecutionService()
        self.approval_service = ApprovalApplicationService(self.execution_service)


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()


def get_execution_service() -> ExecutionService:
    return get_container().execution_service


def get_approval_service() -> ApprovalApplicationService:
    return get_container().approval_service
