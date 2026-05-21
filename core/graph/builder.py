"""LangGraph orchestration builder."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from core.contracts.workflow import WorkflowDefinition
from core.graph.nodes import AgentExecutor, AgentGraphNode
from core.graph.routing import RoutingPolicy, WorkflowRouter
from core.graph.state import LangGraphRuntimeState
from core.graph.supervisor import SupervisorNode


class LangGraphBuilder:
    """Builds a supervisor-routed LangGraph StateGraph from workflow contracts."""

    def __init__(
        self,
        workflow: WorkflowDefinition,
        executors: dict[str, AgentExecutor],
        routing_policy: RoutingPolicy | None = None,
    ) -> None:
        self._workflow = workflow
        self._executors = executors
        self._routing_policy = routing_policy

    def build(self) -> CompiledStateGraph:
        graph = StateGraph(LangGraphRuntimeState)
        executable_agents = tuple(
            agent_name
            for agent_name in self._workflow.agents
            if agent_name in self._executors
        )
        router = WorkflowRouter(
            workflow=self._workflow,
            executable_agents=executable_agents,
            policy=self._routing_policy,
        )
        supervisor = SupervisorNode(router)

        graph.add_node("supervisor", supervisor)
        graph.add_edge(START, "supervisor")

        for agent_name in executable_agents:
            graph.add_node(
                agent_name,
                AgentGraphNode(
                    agent_name=agent_name,
                    executor=self._executors[agent_name],
                ),
            )
            graph.add_edge(agent_name, "supervisor")

        conditional_targets = {agent_name: agent_name for agent_name in executable_agents}
        conditional_targets[END] = END
        graph.add_conditional_edges(
            "supervisor",
            supervisor.route_key,
            conditional_targets,
        )

        return graph.compile()
