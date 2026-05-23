"""Standalone LangGraph runtime worker for recoverable executions."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

from core.agents.model_clients import OpenAIChatModelClient
from core.graph.execution import LangGraphExecutionRuntime
from core.graph.persistence import PostgresWorkflowExecutionRepository, WorkflowExecutionRecord, WorkflowRunStatus
from core.persistence import PostgresJsonDocumentStore


async def main() -> None:
    """Recover persisted running workflows and keep the runtime process alive."""

    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required for the LangGraph runtime worker.")
    store = PostgresJsonDocumentStore(dsn)
    repository = PostgresWorkflowExecutionRepository(store)
    client = OpenAIChatModelClient()
    print("LangGraph runtime worker ready", flush=True)
    while True:
        await _recover_running_records(store, repository, client)
        await asyncio.sleep(int(os.getenv("LANGGRAPH_WORKER_POLL_SECONDS", "10")))


async def _recover_running_records(
    store: PostgresJsonDocumentStore,
    repository: PostgresWorkflowExecutionRepository,
    client: OpenAIChatModelClient,
) -> None:
    records = tuple(
        WorkflowExecutionRecord.model_validate(payload)
        for payload in await store.list(bucket="workflow_executions")
    )
    for record in records:
        if record.status not in {WorkflowRunStatus.RUNNING, WorkflowRunStatus.CREATED}:
            continue
        runtime = LangGraphExecutionRuntime(repository=repository, model_client=client)
        try:
            await runtime.recover(UUID(str(record.execution_id)))
        except Exception as exc:
            failed = record.model_copy(
                update={
                    "status": WorkflowRunStatus.FAILED,
                    "metadata": {**record.metadata, "worker_recovery_error": str(exc)},
                }
            )
            await repository.update(failed)


if __name__ == "__main__":
    asyncio.run(main())
