"""Member B: analyze the shared SNAP Facebook graph on CPU.

Run from the repository with `python community_analysis.py`. The script uses
Member A's edge list and full-precision centrality rankings. Use --raw-snap
to verify a separately downloaded text or gzip edge list against the input.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import statistics
from collections import defaultdict
from pathlib import Path

import graph_tool as gt
import matplotlib
import networkx as nx
import numpy as np
import scipy
from graph_tool.inference import BlockState, minimize_blockmodel_dl

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parent
NODE_COUNT = 4039
EDGE_COUNT = 88234
TOP_K = 20
LOUVAIN_PARAMETERS = dict(weight=None, resolution=1, threshold=1e-7, seed=602610)
SBM_SEEDS = range(602620, 602625)


def load_inputs(edge_path, score_path, raw_path):
    with edge_path.open(encoding="utf-8", newline="") as stream:
        edges = [(int(row["Source"]), int(row["Target"])) for row in csv.DictReader(stream)]
    nodes = sorted({node for edge in edges for node in edge})
    if (
        len(nodes) != NODE_COUNT
        or len(edges) != EDGE_COUNT
        or any(source >= target for source, target in edges)
        or any(left >= right for left, right in zip(edges, edges[1:]))
    ):
        raise ValueError("Expected the sorted, unique, undirected Facebook edges from Member A")
    if raw_path is not None:
        open_raw = gzip.open if raw_path.suffix == ".gz" else open
        with open_raw(raw_path, "rt", encoding="utf-8") as stream:
            raw_edges = {
                tuple(sorted(map(int, line.split()))) for line in stream
                if line.strip() and not line.lstrip().startswith("#")
            }
        if sorted(raw_edges) != edges:
            raise ValueError("The downloaded SNAP file and Member A's edge table differ")

    with score_path.open(encoding="utf-8", newline="") as stream:
        score_rows = list(csv.DictReader(stream))
    scores = {int(row["Node_ID"]): row for row in score_rows}
    if len(score_rows) != NODE_COUNT or sorted(scores) != nodes:
        raise ValueError("Expected one centrality row for every Facebook node")
    for metric in ("PageRank", "Betweenness"):
        ranks = {int(row[f"{metric}_Rank"]) for row in score_rows}
        if ranks != set(range(1, NODE_COUNT + 1)):
            raise ValueError(f"{metric} ranks must contain every rank exactly once")

    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph, nodes, edges, scores


def order_groups(groups):
    """Use one-based labels ordered by decreasing size, then smallest node ID."""
    return sorted(groups, key=lambda group: (-len(group), min(group)))


def membership(groups):
    return {node: label for label, group in enumerate(groups, 1) for node in group}


def fit_sbm(nodes, edges):
    graph = gt.Graph(directed=False)
    graph.add_vertex(len(nodes))
    vertex_index = {node: index for index, node in enumerate(nodes)}
    graph.add_edge_list([(vertex_index[source], vertex_index[target]) for source, target in edges])
    if gt.openmp_enabled():
        gt.openmp_set_num_threads(1)

    trials = []
    best = None
    groups = None
    for seed in SBM_SEEDS:
        gt.seed_rng(seed)
        np.random.seed(seed)
        state = minimize_blockmodel_dl(graph, state=BlockState, state_args={"deg_corr": True})
        score = float(state.entropy())
        if not math.isfinite(score):
            raise RuntimeError(f"Non-finite SBM description length for seed {seed}")
        raw_groups = defaultdict(list)
        for node, block in zip(nodes, state.get_blocks().a, strict=True):
            raw_groups[int(block)].append(node)
        trials.append({"seed": seed, "description_length_nats": score, "blocks": len(raw_groups)})
        print(f"SBM seed {seed}: {len(raw_groups)} blocks, {score:.6f} nats", flush=True)
        if best is None or (score, seed) < best:
            best = (score, seed)
            groups = order_groups(raw_groups.values())
    return groups, best[1], trials


def block_densities(edges, groups, labels):
    counts = np.zeros((len(groups), len(groups)), dtype=int)
    for source, target in edges:
        left, right = sorted((labels[source] - 1, labels[target] - 1))
        counts[left, right] += 1
    counts += np.triu(counts, k=1).T
    sizes = np.array([len(group) for group in groups])
    possible = np.outer(sizes, sizes)
    np.fill_diagonal(possible, sizes * (sizes - 1) // 2)
    densities = np.full(counts.shape, np.nan)
    np.divide(counts, possible, out=densities, where=possible > 0)
    return counts, densities


def partition_overlap(nodes, community, block):
    overlap = np.zeros((max(community.values()), max(block.values())), dtype=int)
    for node in nodes:
        overlap[community[node] - 1, block[node] - 1] += 1
    same_both = sum(math.comb(int(count), 2) for count in overlap.flat)
    same_community = sum(math.comb(int(size), 2) for size in overlap.sum(axis=1))
    same_block = sum(math.comb(int(size), 2) for size in overlap.sum(axis=0))
    expected = same_community * same_block / math.comb(len(nodes), 2)
    maximum = (same_community + same_block) / 2
    ari = (same_both - expected) / (maximum - expected) if maximum != expected else 1.0
    return overlap, ari


def bridge_statistics(graph, scores, community, block):
    for node, neighbors in graph.adj.items():
        degree = len(neighbors)
        external_communities = [community[v] for v in neighbors if community[v] != community[node]]
        external_blocks = [block[v] for v in neighbors if block[v] != block[node]]
        row = {
            "Node_ID": node,
            "Degree": degree,
            "PageRank_Rank": int(scores[node]["PageRank_Rank"]),
            "Betweenness_Rank": int(scores[node]["Betweenness_Rank"]),
            "Community_ID": community[node],
            "Block_ID": block[node],
            "Cross_Community_Edges": len(external_communities),
            "Cross_Community_Fraction": len(external_communities) / degree,
            "Other_Communities": len(set(external_communities)),
            "Cross_Block_Edges": len(external_blocks),
            "Cross_Block_Fraction": len(external_blocks) / degree,
            "Other_Blocks": len(set(external_blocks)),
        }
        row["PageRank_Top20"] = int(row["PageRank_Rank"] <= TOP_K)
        row["Betweenness_Top20"] = int(row["Betweenness_Rank"] <= TOP_K)
        yield row


def summarize_bridges(rows):
    if not rows:
        return None
    return {
        "nodes": len(rows),
        "mean_degree": statistics.mean(row["Degree"] for row in rows),
        "distinct_communities": len({row["Community_ID"] for row in rows}),
        "distinct_blocks": len({row["Block_ID"] for row in rows}),
        **{
            f"mean_{field.lower()}": statistics.mean(row[field] for row in rows)
            for field in (
                "Cross_Community_Edges", "Cross_Community_Fraction", "Other_Communities",
                "Cross_Block_Edges", "Cross_Block_Fraction", "Other_Blocks",
            )
        },
    }


def save_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def group_ticks(axis, count, orientation):
    positions = list(range(0, count, max(1, math.ceil(count / 10))))
    if positions[-1] != count - 1:
        positions.append(count - 1)
    set_ticks = axis.set_xticks if orientation == "x" else axis.set_yticks
    set_ticks(positions, [position + 1 for position in positions])


def save_figure(fig, path):
    fig.savefig(path, metadata={"CreationDate": None})
    plt.close(fig)


def make_figures(directory, communities, blocks, density, overlap, top_rows):
    plt.rcParams.update({
        "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.labelcolor": "#213142", "text.color": "#213142", "pdf.fonttype": 42,
    })

    fig, axis = plt.subplots(figsize=(6.4, 2.6), layout="constrained")
    for groups, name, color, marker in (
        (communities, "Louvain", "#196082", "o"),
        (blocks, "Degree-corrected SBM", "#ad541b", "s"),
    ):
        axis.plot(range(1, len(groups) + 1), [len(group) for group in groups],
                  label=name, color=color, marker=marker, markersize=3.5, linewidth=1.4)
    axis.set(xlabel="Group rank by size", ylabel="Nodes per group", yscale="log")
    axis.set_xticks([1, *range(10, max(len(communities), len(blocks)) + 1, 10)])
    axis.grid(axis="y", alpha=0.22)
    axis.legend(frameon=False)
    save_figure(fig, directory / "partition_sizes.pdf")

    fig, axis = plt.subplots(figsize=(5.5, 4.5), layout="constrained")
    cmap = plt.get_cmap("viridis").with_extremes(bad="#7c8591", under="#edf0f2")
    # A positive floor below the smallest observed density gives zeros their own color.
    positive = density[density > 0]
    image = axis.imshow(
        np.where(density == 0, positive.min() / 2, density),
        cmap=cmap, norm=LogNorm(vmin=float(positive.min()), vmax=float(positive.max())),
        interpolation="nearest",
    )
    fig.colorbar(image, ax=axis, label="Positive edge density", shrink=0.82)
    axis.set(xlabel="SBM block", ylabel="SBM block")
    group_ticks(axis, len(blocks), "x")
    group_ticks(axis, len(blocks), "y")
    save_figure(fig, directory / "block_connectivity_heatmap.pdf")

    fig, axis = plt.subplots(figsize=(6.4, 3.1), layout="constrained")
    normalized = overlap / overlap.sum(axis=1, keepdims=True)
    image = axis.imshow(normalized, vmin=0, vmax=1, cmap="Blues",
                        aspect="auto", interpolation="nearest")
    bar = fig.colorbar(image, ax=axis, label="Share of Louvain community")
    bar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    axis.set(xlabel="SBM block", ylabel="Louvain community")
    group_ticks(axis, len(blocks), "x")
    axis.set_yticks(range(len(communities)), range(1, len(communities) + 1))
    save_figure(fig, directory / "partition_overlap.pdf")

    fig, axis = plt.subplots(figsize=(6.4, 3.3), layout="constrained")
    for page, between, label, color, marker in (
        (1, 0, "PageRank only", "#196082", "o"),
        (0, 1, "Betweenness only", "#ad541b", "^"),
        (1, 1, "Both Top-20 lists", "#574486", "s"),
    ):
        group = [row for row in top_rows
                 if (row["PageRank_Top20"], row["Betweenness_Top20"]) == (page, between)]
        axis.scatter([row["Cross_Community_Fraction"] for row in group],
                     [row["Cross_Block_Fraction"] for row in group],
                     s=32, label=label, c=color, marker=marker,
                     edgecolors="white", linewidths=0.4, zorder=3)
    max_fraction = max(row["Cross_Community_Fraction"] for row in top_rows)
    axis.set(xlabel="Incident edges crossing Louvain communities",
             ylabel="Incident edges crossing SBM blocks",
             xlim=(-0.03, min(1.04, max_fraction + 0.05)), ylim=(-0.04, 1.04))
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    axis.grid(alpha=0.22)
    axis.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=3)
    save_figure(fig, directory / "top20_bridging.pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edges", type=Path, default=ROOT / "facebook_edges.csv")
    parser.add_argument("--centrality", type=Path, default=ROOT / "centrality_scores.csv")
    parser.add_argument("--raw-snap", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()

    graph, nodes, edges, scores = load_inputs(args.edges, args.centrality, args.raw_snap)
    communities = order_groups(nx.community.louvain_communities(graph, **LOUVAIN_PARAMETERS))
    modularity = nx.community.modularity(graph, communities, weight=None, resolution=1)
    blocks, best_seed, trials = fit_sbm(nodes, edges)
    community_labels = membership(communities)
    block_labels = membership(blocks)
    counts, density = block_densities(edges, blocks, block_labels)
    overlap, ari = partition_overlap(nodes, community_labels, block_labels)

    rows = list(bridge_statistics(graph, scores, community_labels, block_labels))
    top_rows = [row for row in rows if row["PageRank_Top20"] or row["Betweenness_Top20"]]
    pagerank_rows = [row for row in top_rows if row["PageRank_Top20"]]
    betweenness_rows = [row for row in top_rows if row["Betweenness_Top20"]]
    shared_rows = [row for row in pagerank_rows if row["Betweenness_Top20"]]
    output = args.output_dir
    figures = output / "community_figures"
    figures.mkdir(parents=True, exist_ok=True)
    save_csv(output / "louvain_communities.csv", ("Node_ID", "Community_ID"),
             ((node, community_labels[node]) for node in nodes))
    save_csv(output / "sbm_block_labels.csv", ("Node_ID", "Block_ID"),
             ((node, block_labels[node]) for node in nodes))
    save_csv(output / "block_connectivity_matrix.csv", ("Block_ID", *range(1, len(blocks) + 1)),
             ([label, *(repr(float(value)) if np.isfinite(value) else "" for value in values)]
              for label, values in enumerate(density, 1)))
    columns = list(top_rows[0])
    save_csv(output / "bridge_analysis.csv", columns,
             ([row[column] for column in columns] for row in top_rows))
    summary = {
        "input": {
            "nodes": len(nodes),
            "edges": len(edges),
            "edges_sha256": hashlib.sha256(args.edges.read_bytes()).hexdigest(),
            "centrality_sha256": hashlib.sha256(args.centrality.read_bytes()).hexdigest(),
        },
        "environment": {
            "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(),
            "networkx": nx.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "graph_tool": gt.__version__,
            "matplotlib": matplotlib.__version__,
            "sbm_threads": 1,
        },
        "louvain": {
            "parameters": LOUVAIN_PARAMETERS,
            "community_sizes": [len(group) for group in communities],
            "modularity": modularity,
            "within_community_edges": sum(
                community_labels[u] == community_labels[v] for u, v in edges),
        },
        "sbm": {
            "degree_corrected": True,
            "selected_seed": best_seed,
            "trials": trials,
            "block_sizes": [len(group) for group in blocks],
            "within_block_edges": int(np.trace(counts)),
            "empty_block_pairs": int(np.count_nonzero(np.triu(counts == 0, k=1))),
            "disconnected_induced_blocks": sum(
                not nx.is_connected(graph.subgraph(group)) for group in blocks),
        },
        "adjusted_rand_index": ari,
        "bridge_profiles": {
            "all_nodes": summarize_bridges(rows),
            "pagerank_top20": summarize_bridges(pagerank_rows),
            "betweenness_top20": summarize_bridges(betweenness_rows),
            "shared_top20": summarize_bridges(shared_rows),
            "pagerank_only": summarize_bridges([row for row in pagerank_rows
                                               if not row["Betweenness_Top20"]]),
            "betweenness_only": summarize_bridges([row for row in betweenness_rows
                                                  if not row["PageRank_Top20"]]),
        },
    }
    (output / "community_analysis_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    make_figures(figures, communities, blocks, density, overlap, top_rows)
    print(f"Louvain: {len(communities)} communities, modularity {modularity:.6f}")
    print(f"Selected SBM seed: {best_seed}; adjusted Rand index: {ari:.6f}")


if __name__ == "__main__":
    main()
