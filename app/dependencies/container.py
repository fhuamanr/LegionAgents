"""Application dependency container."""

from functools import lru_cache

from app.services.execution_service import ExecutionService


class AppContainer:
    """Application service container."""

    def __init__(self) -> None:
        self.execution_service = ExecutionService()


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()


def get_execution_service() -> ExecutionService:
    return get_container().execution_service

