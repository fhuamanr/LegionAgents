"""Repository graph generation."""

from core.contracts.repository_intelligence import ModuleDependency, ModuleNode, RepositoryGraph


class RepositoryGraphGenerator:
    """Creates repository graph contracts from nodes and dependency edges."""

    async def generate(
        self,
        nodes: tuple[ModuleNode, ...],
        edges: tuple[ModuleDependency, ...],
    ) -> RepositoryGraph:
        """Generate a normalized repository graph."""

        known_nodes = {node.id for node in nodes}
        external_nodes = {
            edge.target
            for edge in edges
            if edge.target not in known_nodes and not edge.target.startswith(".") and edge.target
        }
        all_nodes = list(nodes)
        all_nodes.extend(
            ModuleNode(id=target, label=target, path=target, kind="external")
            for target in sorted(external_nodes)
        )
        return RepositoryGraph(
            nodes=tuple(all_nodes),
            edges=edges,
            metadata={
                "node_count": len(all_nodes),
                "edge_count": len(edges),
                "external_dependency_count": len(external_nodes),
            },
        )
