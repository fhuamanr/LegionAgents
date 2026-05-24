import pytest

from core.context_engineering.models import ContextEngineeringConfig
from core.persistence import PostgresJsonDocumentStore
from core.agents.providers import ProviderRegistry, RoutingModelClient


def test_context_engineering_config_allows_repository_file_limit_zero() -> None:
    config = ContextEngineeringConfig(repository_file_limit=0)
    assert config.repository_file_limit == 0


def test_worker_model_client_uses_provider_registry_without_openai_key() -> None:
    store = PostgresJsonDocumentStore("postgresql://placeholder:placeholder@localhost:5432/placeholder")
    registry = ProviderRegistry(store)
    client = RoutingModelClient(registry)
    assert client is not None

