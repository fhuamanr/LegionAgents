"""Factories for default workflow topology."""

from core.contracts.workflow import WorkflowDefinition, WorkflowEdge


def build_default_delivery_workflow(available_agents: tuple[str, ...]) -> WorkflowDefinition:
    """Build the default delivery workflow using only agents present in the repo."""

    preferred_order = ("ba", "architect", "developer", "qa", "docs", "pr")
    agents = tuple(agent for agent in preferred_order if agent in available_agents)
    edge_candidates = (
        WorkflowEdge(source="ba", target="architect"),
        WorkflowEdge(source="architect", target="developer"),
        WorkflowEdge(source="developer", target="qa"),
        WorkflowEdge(source="qa", target="developer", condition="defects_found"),
        WorkflowEdge(source="developer", target="docs"),
        WorkflowEdge(source="qa", target="docs", condition="validated"),
        WorkflowEdge(source="docs", target="pr"),
    )
    agent_set = set(agents)
    edges = tuple(
        edge for edge in edge_candidates if edge.source in agent_set and edge.target in agent_set
    )
    return WorkflowDefinition(name="default_delivery_workflow", agents=agents, edges=edges)
