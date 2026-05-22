"""Real LangGraph workflow execution runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from core.agents.runtime import AgentModelClient, AgentRuntime
from core.contracts.agents import AgentStatus
from core.contracts.execution import AgentExecutionRequest, AgentExecutionResult
from core.contracts.states import WorkflowExecutionState
from core.graph.persistence import (
    InMemoryWorkflowExecutionRepository,
    WorkflowCheckpoint,
    WorkflowExecutionRecord,
    WorkflowExecutionRepository,
    WorkflowRunStatus,
)
from core.graph.runtime_agents import build_default_agent_runtimes


DEFAULT_DELIVERY_SEQUENCE: tuple[str, ...] = ("ba", "architect", "developer", "qa", "docs", "pr")


class RealWorkflowRuntimeState(TypedDict, total=False):
    """LangGraph state used by the executable workflow runtime."""

    execution_id: UUID
    workflow_state: WorkflowExecutionState
    status: str
    next_agent: str | None
    last_agent: str | None
    attempts: dict[str, int]
    errors: list[str]
    metadata: dict[str, Any]


class WorkflowRunResult(WorkflowExecutionRecord):
    """Final execution record returned by workflow runtime calls."""


WorkflowEventHook = Callable[[str, RealWorkflowRuntimeState], Awaitable[None]]


class LangGraphExecutionRuntime:
    """Executes the default multi-agent delivery workflow through LangGraph."""

    def __init__(
        self,
        agent_runtimes: dict[str, AgentRuntime] | None = None,
        model_client: AgentModelClient | None = None,
        project_root: Path | None = None,
        repository: WorkflowExecutionRepository | None = None,
        max_agent_attempts: int = 2,
        max_qa_rejection_loops: int = 2,
        event_hook: WorkflowEventHook | None = None,
        compiled_graph: CompiledStateGraph | None = None,
    ) -> None:
        self._agent_runtimes = agent_runtimes or build_default_agent_runtimes(
            project_root=project_root,
            model_client=model_client,
        )
        self._repository = repository or InMemoryWorkflowExecutionRepository()
        self._max_agent_attempts = max_agent_attempts
        self._max_qa_rejection_loops = max_qa_rejection_loops
        self._event_hook = event_hook
        self._compiled_graph = compiled_graph

    @property
    def repository(self) -> WorkflowExecutionRepository:
        """Expose persistence boundary for application services and tests."""

        return self._repository

    async def start(
        self,
        task: str,
        *,
        workflow_id: UUID | None = None,
        execution_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Create and execute a workflow from the beginning."""

        workflow_state = WorkflowExecutionState(
            workflow_id=workflow_id or uuid4(),
            task=task,
            metadata={**(metadata or {}), "execution_id": str(execution_id or uuid4())},
        )
        execution_uuid = UUID(str(workflow_state.metadata["execution_id"]))
        record = WorkflowExecutionRecord(
            execution_id=execution_uuid,
            workflow_id=workflow_state.workflow_id,
            task=task,
            status=WorkflowRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            next_agent=DEFAULT_DELIVERY_SEQUENCE[0],
            metadata=metadata or {},
        )
        await self._repository.create(record)
        initial_state: RealWorkflowRuntimeState = {
            "execution_id": execution_uuid,
            "workflow_state": workflow_state,
            "status": WorkflowRunStatus.RUNNING.value,
            "next_agent": DEFAULT_DELIVERY_SEQUENCE[0],
            "last_agent": None,
            "attempts": {},
            "errors": [],
            "metadata": metadata or {},
        }
        final_state = await self._graph.ainvoke(initial_state)
        return await self._finalize(final_state)

    async def recover(self, execution_id: UUID) -> WorkflowRunResult:
        """Resume execution from the latest persisted checkpoint."""

        existing_record = await self._repository.get(execution_id)
        if existing_record.status == WorkflowRunStatus.CANCELLED:
            return WorkflowRunResult.model_validate(existing_record)
        checkpoint = await self._repository.latest_checkpoint(execution_id)
        if checkpoint is None:
            raise ValueError(f"No checkpoint exists for execution {execution_id}")
        if checkpoint.status in {
            WorkflowRunStatus.COMPLETED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
        }:
            terminal_record = await self._repository.get(execution_id)
            return WorkflowRunResult(**terminal_record.model_dump())
        record = await self._repository.get(execution_id)
        runtime_metadata = dict(record.metadata.get("runtime_metadata", {}))
        runtime_metadata.pop("pause_after_agent", None)
        state: RealWorkflowRuntimeState = {
            "execution_id": execution_id,
            "workflow_state": checkpoint.state,
            "status": WorkflowRunStatus.RUNNING.value,
            "next_agent": checkpoint.next_agent,
            "last_agent": checkpoint.active_agent,
            "attempts": dict(record.metadata.get("attempts", {})),
            "errors": list(record.metadata.get("errors", [])),
            "metadata": runtime_metadata,
        }
        updated = record.model_copy(
            update={
                "status": WorkflowRunStatus.RUNNING,
                "started_at": record.started_at or datetime.now(timezone.utc),
                "next_agent": checkpoint.next_agent,
            }
        )
        await self._repository.update(updated)
        final_state = await self._graph.ainvoke(state)
        return await self._finalize(final_state)

    async def cancel(self, execution_id: UUID, reason: str | None = None) -> WorkflowExecutionRecord:
        """Request cancellation for an execution."""

        return await self._repository.cancel(execution_id, reason)

    @property
    def _graph(self) -> CompiledStateGraph:
        if self._compiled_graph is None:
            graph = StateGraph(RealWorkflowRuntimeState)
            graph.add_node("router", self._router_node)
            graph.add_edge(START, "router")
            for agent_name in DEFAULT_DELIVERY_SEQUENCE:
                graph.add_node(agent_name, self._agent_node(agent_name))
                graph.add_edge(agent_name, "router")
            targets = {agent_name: agent_name for agent_name in DEFAULT_DELIVERY_SEQUENCE}
            targets[END] = END
            graph.add_conditional_edges("router", self._route_from_router, targets)
            self._compiled_graph = graph.compile()
        return self._compiled_graph

    async def _router_node(self, state: RealWorkflowRuntimeState) -> RealWorkflowRuntimeState:
        execution_id = state["execution_id"]
        record = await self._repository.get(execution_id)
        if record.status == WorkflowRunStatus.CANCELLED:
            return await self._persist_state(
                state,
                status=WorkflowRunStatus.CANCELLED,
                next_agent=None,
            )

        next_agent = self._next_agent(state)
        status = WorkflowRunStatus(str(state.get("status", WorkflowRunStatus.RUNNING.value)))
        if status == WorkflowRunStatus.RUNNING and next_agent is None:
            status = WorkflowRunStatus.COMPLETED
        if self._should_pause(state, next_agent):
            status = WorkflowRunStatus.PAUSED
        return await self._persist_state(state, status=status, next_agent=next_agent)

    def _route_from_router(self, state: RealWorkflowRuntimeState) -> str:
        if state.get("status") != WorkflowRunStatus.RUNNING.value:
            return END
        return state.get("next_agent") or END

    def _agent_node(self, agent_name: str) -> Callable[[RealWorkflowRuntimeState], Awaitable[RealWorkflowRuntimeState]]:
        async def run(state: RealWorkflowRuntimeState) -> RealWorkflowRuntimeState:
            return await self._execute_agent(agent_name, state)

        return run

    async def _execute_agent(
        self,
        agent_name: str,
        state: RealWorkflowRuntimeState,
    ) -> RealWorkflowRuntimeState:
        execution_id = state["execution_id"]
        record = await self._repository.get(execution_id)
        if record.status == WorkflowRunStatus.CANCELLED:
            return await self._persist_state(
                state,
                status=WorkflowRunStatus.CANCELLED,
                next_agent=None,
            )

        workflow_state = state["workflow_state"]
        attempts = dict(state.get("attempts", {}))
        attempts[agent_name] = attempts.get(agent_name, 0) + 1
        request = AgentExecutionRequest(
            execution_id=execution_id,
            workflow_id=workflow_state.workflow_id,
            agent_name=agent_name,
            task=workflow_state.task,
            upstream_artifacts=workflow_state.artifacts,
            metadata={
                **state.get("metadata", {}),
                "agent_attempt": attempts[agent_name],
                "workflow_attempts": attempts,
            },
        )

        if attempts[agent_name] > 1:
            await self._emit("retry_started", {**state, "next_agent": agent_name, "attempts": attempts})
        await self._emit("agent_started", {**state, "next_agent": agent_name, "attempts": attempts})
        try:
            result = await self._agent_runtimes[agent_name].execute(request)
        except Exception as exc:
            result = AgentExecutionResult(
                execution_id=execution_id,
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                errors=(str(exc),),
                metadata={"route_signal": "retry"},
            )

        updated_workflow_state = self._apply_result(workflow_state, result, attempts[agent_name])
        errors = list(state.get("errors", []))
        if result.errors:
            errors.extend(result.errors)
        updated_state: RealWorkflowRuntimeState = {
            **state,
            "workflow_state": updated_workflow_state,
            "last_agent": agent_name,
            "attempts": attempts,
            "errors": errors,
            "metadata": dict(state.get("metadata", {})),
        }
        await self._emit(
            "agent_completed" if result.status == AgentStatus.COMPLETED else "agent_failed",
            updated_state,
        )
        latest_record = await self._repository.get(execution_id)
        if latest_record.status == WorkflowRunStatus.CANCELLED:
            return await self._persist_state(
                updated_state,
                status=WorkflowRunStatus.CANCELLED,
                next_agent=None,
                active_agent=agent_name,
            )
        return await self._persist_state(
            updated_state,
            status=WorkflowRunStatus.RUNNING,
            next_agent=None,
            active_agent=agent_name,
        )

    def _apply_result(
        self,
        workflow_state: WorkflowExecutionState,
        result: AgentExecutionResult,
        attempt: int,
    ) -> WorkflowExecutionState:
        from core.graph.nodes import AgentGraphNode

        node = AgentGraphNode(result.agent_name, _ResultReplayAgentExecutor(result))
        running = node._mark_running(workflow_state, datetime.now(timezone.utc))
        previous = running.agent_states[result.agent_name]
        running = running.model_copy(
            update={
                "agent_states": {
                    **running.agent_states,
                    result.agent_name: previous.model_copy(update={"attempt": attempt}),
                }
            }
        )
        return node._apply_result(running, result)

    def _next_agent(self, state: RealWorkflowRuntimeState) -> str | None:
        status = WorkflowRunStatus(str(state.get("status", WorkflowRunStatus.RUNNING.value)))
        if status != WorkflowRunStatus.RUNNING:
            return None
        last_agent = state.get("last_agent")
        workflow_state = state["workflow_state"]
        if last_agent is None:
            return state.get("next_agent") or DEFAULT_DELIVERY_SEQUENCE[0]

        snapshot = workflow_state.agent_states.get(last_agent)
        attempts = dict(state.get("attempts", {}))
        if snapshot is not None and snapshot.status == AgentStatus.FAILED:
            if attempts.get(last_agent, 0) < self._max_agent_attempts:
                return last_agent
            return self._mark_terminal(state, WorkflowRunStatus.FAILED)

        route_signal = snapshot.metadata.get("route_signal") if snapshot else None
        if last_agent == "qa" and route_signal == "reject":
            rejection_count = int(workflow_state.metadata.get("qa_rejection_count", 0))
            if rejection_count <= self._max_qa_rejection_loops:
                return "developer"
            return self._mark_terminal(state, WorkflowRunStatus.FAILED)

        index = DEFAULT_DELIVERY_SEQUENCE.index(last_agent)
        if index + 1 >= len(DEFAULT_DELIVERY_SEQUENCE):
            return None
        return DEFAULT_DELIVERY_SEQUENCE[index + 1]

    def _should_pause(self, state: RealWorkflowRuntimeState, next_agent: str | None) -> bool:
        pause_after_agent = state.get("metadata", {}).get("pause_after_agent")
        if pause_after_agent is None:
            return False
        if state.get("last_agent") != pause_after_agent:
            return False
        return next_agent is not None

    def _mark_terminal(self, state: RealWorkflowRuntimeState, status: WorkflowRunStatus) -> Literal[None]:
        state["status"] = status.value
        return None

    async def _persist_state(
        self,
        state: RealWorkflowRuntimeState,
        *,
        status: WorkflowRunStatus,
        next_agent: str | None,
        active_agent: str | None = None,
    ) -> RealWorkflowRuntimeState:
        execution_id = state["execution_id"]
        record = await self._repository.get(execution_id)
        if record.status == WorkflowRunStatus.CANCELLED and status != WorkflowRunStatus.CANCELLED:
            status = WorkflowRunStatus.CANCELLED
            next_agent = None
        checkpoint = WorkflowCheckpoint(
            execution_id=execution_id,
            workflow_id=state["workflow_state"].workflow_id,
            sequence=len(record.checkpoints),
            status=status,
            active_agent=active_agent or state.get("last_agent"),
            next_agent=next_agent,
            state=state["workflow_state"],
            metadata={
                "attempts": dict(state.get("attempts", {})),
                "errors": list(state.get("errors", [])),
            },
        )
        await self._repository.append_checkpoint(checkpoint)
        updated = WorkflowExecutionRecord.model_validate(await self._repository.get(execution_id))
        await self._repository.update(
            updated.model_copy(
                update={
                    "status": status,
                    "active_agent": active_agent or state.get("last_agent"),
                    "next_agent": next_agent,
                    "completed_at": datetime.now(timezone.utc)
                    if status in {WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}
                    else updated.completed_at,
                    "metadata": {
                        **updated.metadata,
                        "attempts": dict(state.get("attempts", {})),
                        "errors": list(state.get("errors", [])),
                        "runtime_metadata": dict(state.get("metadata", {})),
                    },
                }
            )
        )
        state["status"] = status.value
        state["next_agent"] = next_agent
        return state

    async def _finalize(self, state: RealWorkflowRuntimeState) -> WorkflowRunResult:
        record = await self._repository.get(state["execution_id"])
        status = WorkflowRunStatus(str(state.get("status", record.status.value)))
        if record.status != status:
            now = datetime.now(timezone.utc)
            record = await self._repository.update(
                record.model_copy(
                    update={
                        "status": status,
                        "completed_at": now
                        if status in {WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}
                        else record.completed_at,
                        "updated_at": now,
                    }
                )
            )
        return WorkflowRunResult(**record.model_dump())

    async def _emit(self, event_name: str, state: RealWorkflowRuntimeState) -> None:
        if self._event_hook is not None:
            await self._event_hook(event_name, state)


class _ResultReplayAgentExecutor:
    """Adapter used only to reuse graph state transition code."""

    def __init__(self, result: AgentExecutionResult) -> None:
        self._result = result

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        return self._result
