"""Shared directed live-edge implementation of Independent Cascade."""

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order


@dataclass
class PreparedIC:
    """Canonical topology shared by all conditions of an experiment."""

    nodes: tuple
    node_index: dict
    sources: np.ndarray
    targets: np.ndarray

    @classmethod
    def from_graph(cls, graph):
        if graph.is_directed() or graph.is_multigraph():
            raise ValueError("Expected a simple undirected graph")
        nodes = tuple(sorted(graph))
        node_index = {node: index for index, node in enumerate(nodes)}
        arcs = [
            (node_index[node], node_index[neighbor])
            for node in nodes
            for neighbor in sorted(graph[node])
            if node != neighbor
        ]
        sources, targets = np.asarray(arcs, dtype=np.int32).reshape(-1, 2).T
        return cls(nodes, node_index, sources, targets)

    def live_arcs(self, live_edge_seed):
        """Generate U in canonical (source ID, target ID) order."""
        rng = np.random.Generator(np.random.PCG64(live_edge_seed))
        return rng.random(self.sources.size)

    def cascade(self, seeds, p, arc_uniforms, removed_nodes=()):
        if not 0 <= p <= 1:
            raise ValueError("p must be between 0 and 1")
        seed_ids = sorted({self.node_index[node] for node in seeds})
        blocked = {self.node_index[node] for node in removed_nodes}
        if not seed_ids or blocked.intersection(seed_ids):
            raise ValueError("Initial seeds must be nonempty and survive removal")

        n = len(self.nodes)
        survives = np.ones(n, dtype=bool)
        survives[list(blocked)] = False
        live = (arc_uniforms < p) & survives[self.sources] & survives[self.targets]
        live_sources = self.sources[live]
        indices = np.concatenate((self.targets[live], np.asarray(seed_ids, dtype=np.int32)))
        # Add one super-source with arcs to the initial seeds for multi-source BFS.
        counts = np.bincount(live_sources, minlength=n)
        offsets = np.concatenate(([0], np.cumsum(counts), [indices.size])).astype(np.int32)
        adjacency = csr_matrix((np.ones(indices.size, dtype=np.int8), indices, offsets),
                               shape=(n + 1, n + 1))
        order, parents = breadth_first_order(adjacency, n, directed=True)
        reached = order[1:]

        # Accumulate BFS tree distances by repeatedly jumping to each parent's parent.
        parents[n] = n
        distances = np.zeros(n + 1, dtype=np.int32)
        distances[reached] = 1
        while np.any(parents[reached] != n):
            distances[reached] += distances[parents[reached]]
            parents[reached] = parents[parents[reached]]
        round_counts = np.bincount(distances[reached] - 1).tolist()
        return {
            "final_activated": len(reached),
            "activated_fraction": len(reached) / n,
            "rounds": len(round_counts) - 1,
            "round_counts": round_counts,
        }


def simulate_ic(G, seeds, p, live_edge_seed, removed_nodes=None):
    """Accept the original NetworkX Graph or its reusable PreparedIC topology."""
    topology = G if isinstance(G, PreparedIC) else PreparedIC.from_graph(G)
    arc_uniforms = topology.live_arcs(live_edge_seed)
    return topology.cascade(seeds, p, arc_uniforms, () if removed_nodes is None else removed_nodes)


def intervention_nodes(nodes, pagerank_top, betweenness_top, trial_id, seed_offset=0):
    """Draw the common seeds and random-removal set for Members D and E."""
    nodes = set(nodes)
    eligible = sorted(nodes.difference(pagerank_top, betweenness_top))
    seed_rng = np.random.default_rng(602600 + trial_id + seed_offset)
    seeds = sorted(seed_rng.choice(eligible, size=20, replace=False).tolist())
    removal_rng = np.random.default_rng(602700 + trial_id + seed_offset)
    removed = sorted(removal_rng.choice(sorted(nodes.difference(seeds)), size=20,
                                        replace=False).tolist())
    return seeds, removed
