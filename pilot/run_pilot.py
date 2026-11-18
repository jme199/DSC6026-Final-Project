"""Benchmark the full SNAP graph with small trial counts."""

import argparse
import csv
import json
from pathlib import Path
import platform
import resource
import time

import networkx as nx
import numpy as np
import scipy
from scipy.sparse.csgraph import shortest_path
from scipy.stats import t

from ic_core import PreparedIC, intervention_nodes, simulate_ic


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pilot"
PROBABILITIES = (0.01, 0.02, 0.05, 0.10, 0.20)
PILOT_OFFSET = 10000
PILOT_REPEATS = 20


def load_inputs(rebuild_centrality):
    graph = nx.read_edgelist(ROOT / "data/raw/facebook_combined.txt.gz", nodetype=int)
    edges = sorted((min(u, v), max(u, v)) for u, v in graph.edges())
    canonical = nx.Graph()
    canonical.add_nodes_from(sorted(graph))
    canonical.add_edges_from(edges)
    assert len(graph) == 4039 and len(edges) == 88234 and not nx.number_of_selfloops(graph)
    scores_path = OUT / "centrality_scores.csv"
    if rebuild_centrality or not scores_path.exists():
        compute_centrality(canonical)
    with scores_path.open(newline="", encoding="utf-8") as file:
        scores = list(csv.DictReader(file))
    assert len(scores) == len(graph) and {int(row["Node_ID"]) for row in scores} == set(graph)
    return canonical, {
        column: sorted(int(row["Node_ID"]) for row in scores if int(row[column + "_Rank"]) <= 20)
        for column in ("PageRank", "Betweenness")
    }


def compute_centrality(graph):
    start = time.perf_counter()
    pagerank = nx.pagerank(graph, alpha=0.85, tol=1e-8, max_iter=1000, weight=None)
    print(f"PageRank: {time.perf_counter() - start:.2f}s", flush=True)
    start = time.perf_counter()
    betweenness = nx.betweenness_centrality(graph, normalized=True, weight=None, endpoints=False)
    print(f"Exact betweenness: {time.perf_counter() - start:.2f}s", flush=True)
    scores = {"Degree": dict(graph.degree), "Betweenness": betweenness, "PageRank": pagerank}
    ranks = {
        name: {node: rank for rank, node in enumerate(sorted(graph, key=lambda v: (-values[v], v)), 1)}
        for name, values in scores.items()
    }
    rows = [
        {
            "Node_ID": node,
            **{name: values[node] for name, values in scores.items()},
            **{f"{name}_Rank": rank[node] for name, rank in ranks.items()},
        }
        for node in graph
    ]
    write_csv("centrality_scores.csv", rows)


def verify_ic():
    graph = nx.path_graph(8)
    assert simulate_ic(graph, [0, 3], 0, 42)["round_counts"] == [2]
    assert simulate_ic(graph, [0, 3], 1, 42)["round_counts"] == [2, 3, 1, 1, 1]
    assert simulate_ic(graph, [0], 1, 42, [3])["round_counts"] == [1, 1, 1]
    graph.add_edges_from([(0, 6), (2, 5)])
    topology = PreparedIC.from_graph(graph)
    for seed in range(25):
        uniforms = topology.live_arcs(seed)
        live = nx.DiGraph()
        live.add_nodes_from(graph)
        live.add_edges_from(zip(topology.sources[uniforms < 0.4],
                                topology.targets[uniforms < 0.4]))
        live.remove_node(2)
        live.add_edges_from([(8, 0), (8, 5)])
        distances = nx.single_source_shortest_path_length(live, 8)
        expected = np.bincount([d - 1 for d in distances.values() if d]).tolist()
        assert simulate_ic(topology, [0, 5], 0.4, seed, [2])["round_counts"] == expected
        assert simulate_ic(nx.Graph(reversed(list(graph.edges()))), [0, 5], 0.4, seed, [2])[
            "round_counts"] == expected


def write_csv(name, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    sd = float(np.std(values, ddof=1))
    return {
        "mean": float(np.mean(values)),
        "sd": sd,
        "halfwidth_50": float(t.ppf(0.975, 49) * sd / np.sqrt(50)),
        "halfwidth_200": float(t.ppf(0.975, 199) * sd / np.sqrt(200)),
    }


def benchmark_ic(graph, top):
    start = time.perf_counter()
    topology = PreparedIC.from_graph(graph)
    prepare_seconds = time.perf_counter() - start
    rows_c, rows_e, summary = [], [], []
    for p in PROBABILITIES:
        timings_c, timings_e, trials_c, trials_e = [], [], [], []
        for r in range(PILOT_REPEATS):
            start = time.perf_counter()
            seed_c = 602900 + r + PILOT_OFFSET
            uniforms = topology.live_arcs(seed_c)
            c = {name: topology.cascade(seeds, p, uniforms) for name, seeds in top.items()}
            timings_c.append(time.perf_counter() - start)

            start = time.perf_counter()
            seeds, random_nodes = intervention_nodes(
                graph, top["PageRank"], top["Betweenness"], r, PILOT_OFFSET)
            seed_e = 602800 + r + PILOT_OFFSET
            uniforms = topology.live_arcs(seed_e)
            conditions = {"Original": [], **top, "Random": random_nodes}
            e = {name: topology.cascade(seeds, p, uniforms, removed)
                 for name, removed in conditions.items()}
            timings_e.append(time.perf_counter() - start)
            baseline = e["Original"]["final_activated"]
            assert all(out["final_activated"] <= baseline for out in e.values())
            assert all(sum(out["round_counts"]) == out["final_activated"]
                       for out in (*c.values(), *e.values()))
            trials_c.append([out["final_activated"] for out in c.values()])
            trials_e.append([out["final_activated"] for out in e.values()])
            for name, out in c.items():
                rows_c.append(dict(Trial_ID=r, Probability_p=p, Seed_Strategy=name,
                                   Live_Edge_Seed=seed_c, Final_Activated=out["final_activated"],
                                   Activated_Fraction=out["activated_fraction"], Rounds=out["rounds"],
                                   Round_Counts=json.dumps(out["round_counts"])))
            for name, out in e.items():
                rows_e.append(dict(Trial_ID=r, Probability_p=p, Removal_Strategy=name,
                                   Initial_Seeds=json.dumps(seeds), Removed_Nodes=json.dumps(conditions[name]),
                                   Live_Edge_Seed=seed_e, Final_Activated=out["final_activated"],
                                   Activated_Fraction=out["activated_fraction"], Rounds=out["rounds"],
                                   Round_Counts=json.dumps(out["round_counts"]),
                                   Diffusion_Drop_Pct=100 * (baseline - out["final_activated"]) / baseline))
        c = np.asarray(trials_c)
        e = np.asarray(trials_e)
        summary.append({
            "p": p,
            "C_seconds_per_pair_mean": float(np.mean(timings_c)),
            "E_seconds_per_block_mean": float(np.mean(timings_e)),
            "C_mean_reach_pct": (100 * c.mean(axis=0) / len(graph)).tolist(),
            "E_mean_reach_pct": (100 * e.mean(axis=0) / len(graph)).tolist(),
            "C_paired_difference_nodes": stats(c[:, 0] - c[:, 1]),
            "E_paired_drop_pct": {
                name: stats(100 * (e[:, 0] - e[:, i]) / e[:, 0])
                for i, name in enumerate(("PageRank", "Betweenness", "Random"), start=1)
            },
            "E_targeted_minus_random_drop_pp": {
                name: stats(100 * (e[:, 3] - e[:, i]) / e[:, 0])
                for i, name in enumerate(("PageRank", "Betweenness"), start=1)
            },
        })
    write_csv("seed_diffusion_trials.csv", rows_c)
    write_csv("intervention_diffusion_trials.csv", rows_e)
    return {"prepare_seconds": prepare_seconds, "by_probability": summary}


def benchmark_structure(graph, top):
    rows = []
    conditions = [("Original", None, []), *((name, None, nodes) for name, nodes in top.items())]
    for r in range(5):
        _, removed = intervention_nodes(graph, top["PageRank"], top["Betweenness"], r, PILOT_OFFSET)
        conditions.append(("Random", r, removed))
    for name, r, removed in conditions:
        start = time.perf_counter()
        working = graph.copy()
        working.remove_nodes_from(removed)
        components = sorted(nx.connected_components(working), key=lambda c: (-len(c), min(c)))
        gcc = sorted(components[0])
        adjacency = nx.to_scipy_sparse_array(working, nodelist=sorted(working), dtype=np.int32,
                                             format="csr")
        indices = np.searchsorted(sorted(working), gcc)
        adjacency = adjacency[indices, :][:, indices].tocsr()
        total = sum(shortest_path(adjacency, directed=False, unweighted=True,
                                  indices=range(i, min(i + 128, len(gcc)))).sum()
                    for i in range(0, len(gcc), 128))
        size = len(gcc)
        rows.append(dict(Trial_ID=r, Removal_Strategy=name, Removed_Nodes=json.dumps(removed),
                         GCC_Size=size, Num_Components=len(components),
                         Avg_Path_Length=total / (size * (size - 1)) if size > 1 else 0,
                         Wall_Seconds=time.perf_counter() - start))
    write_csv("structural_removal_results.csv", rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-centrality", action="store_true")
    args = parser.parse_args()
    verify_ic()
    graph, top = load_inputs(args.rebuild_centrality)
    assert len(top["PageRank"]) == len(top["Betweenness"]) == 20
    ic = benchmark_ic(graph, top)
    print("Completed 600 IC cascades", flush=True)
    structural = benchmark_structure(graph, top)
    start = time.perf_counter()
    communities = nx.community.louvain_communities(graph, weight=None, resolution=1, seed=602610)
    modularity = nx.community.modularity(graph, communities, weight=None, resolution=1)
    louvain_seconds = time.perf_counter() - start
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak_rss *= 1024
    result = {
        "environment": dict(platform=platform.platform(), python=platform.python_version(),
                            numpy=np.__version__, scipy=scipy.__version__, networkx=nx.__version__),
        "pilot_seed_offset": PILOT_OFFSET,
        "pilot_repeats": PILOT_REPEATS,
        "top20": top,
        "ic": ic,
        "structure": structural,
        "louvain": dict(count=len(communities), modularity=modularity, seconds=louvain_seconds),
        "peak_rss_mib": peak_rss / (1024 ** 2),
    }
    (OUT / "benchmark.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
