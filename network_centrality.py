"""DSC6026 Final Project - Member A: Network Construction & Centrality Analysis

Input:
    data/facebook_combined.txt.gz

Outputs (project root):
    facebook_edges.csv
    network_stats.csv
    centrality_scores.csv
    network_figures/*.png
    report/A_network_centrality.md

The script follows the team's protocol:
- undirected, unweighted simple graph
- remove self-loops and duplicate/reversed duplicate edges
- canonical edge order: (min(Source, Target), max(Source, Target))
- Degree centrality = Degree / (N - 1)
- exact normalized betweenness, endpoints=False, weight=None
- PageRank alpha=0.85, tol=1e-8, max_iter=1000, weight=None
- rank by full-precision score descending; ties broken by Node_ID ascending
"""

from __future__ import annotations

import gzip
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib
matplotlib.use("Agg")  # Save figures without requiring an interactive window.
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "facebook_combined.txt.gz"
FIGURE_DIR = BASE_DIR / "network_figures"
REPORT_DIR = BASE_DIR / "report"

EXPECTED_NODES = 4039
EXPECTED_EDGES = 88234
LAYOUT_SEED = 602610

# Centrality parameters required by the team protocol.
PAGERANK_ALPHA = 0.85
PAGERANK_TOL = 1e-8
PAGERANK_MAX_ITER = 1000
TOP_K = 20


# ---------------------------------------------------------------------------
# 1. Read and clean the compressed SNAP edge list
# ---------------------------------------------------------------------------
def read_and_clean_edges(
    file_path: Path,
) -> Tuple[List[Tuple[int, int]], List[int], Dict[str, int]]:
    """Read a .txt.gz edge list and return sorted unique undirected edges.

    Each input row should contain two integer node IDs. Reversed duplicates
    such as (1, 2) and (2, 1) are treated as the same undirected edge.
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"Cannot find the dataset:\n{file_path}\n\n"
            "Please download facebook_combined.txt.gz from SNAP and place it "
            "inside the project's data folder."
        )

    edge_set: set[Tuple[int, int]] = set()
    total_data_lines = 0
    self_loops_removed = 0
    duplicate_edges_removed = 0
    malformed_lines_skipped = 0

    try:
        with gzip.open(file_path, mode="rt", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                total_data_lines += 1
                parts = stripped.split()
                if len(parts) != 2:
                    malformed_lines_skipped += 1
                    continue

                try:
                    u = int(parts[0])
                    v = int(parts[1])
                except ValueError:
                    malformed_lines_skipped += 1
                    continue

                if u == v:
                    self_loops_removed += 1
                    continue

                edge = (min(u, v), max(u, v))
                if edge in edge_set:
                    duplicate_edges_removed += 1
                else:
                    edge_set.add(edge)
    except OSError as exc:
        raise RuntimeError(
            f"Could not read {file_path}. Check that it is the original .gz file "
            "and that the download is complete."
        ) from exc

    edges = sorted(edge_set)
    nodes = sorted({node for edge in edges for node in edge})

    cleaning_info = {
        "Input_Data_Lines": total_data_lines,
        "Self_Loops_Removed": self_loops_removed,
        "Duplicate_Edges_Removed": duplicate_edges_removed,
        "Malformed_Lines_Skipped": malformed_lines_skipped,
    }
    return edges, nodes, cleaning_info


# ---------------------------------------------------------------------------
# 2. Construct the graph and export the standardized edge table
# ---------------------------------------------------------------------------
def build_graph(
    edges: Iterable[Tuple[int, int]], nodes: Iterable[int]
) -> nx.Graph:
    """Build an undirected, unweighted simple NetworkX graph."""
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)

    # Defensive checks: all graph edges must be simple and unweighted.
    if nx.number_of_selfloops(graph) != 0:
        raise ValueError("Self-loops remain after cleaning; please inspect the input.")
    if graph.number_of_edges() != len(set(graph.edges())):
        raise ValueError("Duplicate edges remain after graph construction.")

    return graph


def save_edge_table(edges: List[Tuple[int, int]], output_path: Path) -> None:
    edge_df = pd.DataFrame(edges, columns=["Source", "Target"])
    edge_df.to_csv(output_path, index=False)
    print(f"Saved standardized edge table: {output_path}")


# ---------------------------------------------------------------------------
# 3. Network statistics
# ---------------------------------------------------------------------------
def calculate_network_statistics(
    graph: nx.Graph, cleaning_info: Dict[str, int]
) -> Tuple[Dict[str, float | int], nx.Graph, List[set[int]]]:
    n = graph.number_of_nodes()
    m = graph.number_of_edges()

    if n == 0:
        raise ValueError("The graph has no nodes. Check the downloaded dataset.")

    components = list(nx.connected_components(graph))
    # In a tie, select the component whose minimum Node_ID is smallest.
    gcc_nodes = max(components, key=lambda c: (len(c), -min(c)))
    gcc = graph.subgraph(gcc_nodes)

    average_shortest_path_gcc = (
        nx.average_shortest_path_length(gcc) if gcc.number_of_nodes() > 1 else 0.0
    )

    stats: Dict[str, float | int] = {
        "Nodes": n,
        "Edges": m,
        "Density": nx.density(graph),
        "Average_Degree": sum(dict(graph.degree()).values()) / n,
        "Average_Clustering_Coefficient": nx.average_clustering(graph),
        "Connected_Components": len(components),
        "GCC_Nodes": gcc.number_of_nodes(),
        "GCC_Fraction": gcc.number_of_nodes() / n,
        "Average_Shortest_Path_GCC": average_shortest_path_gcc,
        **cleaning_info,
    }
    return stats, gcc, components


def save_network_statistics(stats: Dict[str, float | int], output_path: Path) -> None:
    pd.DataFrame([stats]).to_csv(output_path, index=False, float_format="%.17g")
    print(f"Saved network statistics: {output_path}")


# ---------------------------------------------------------------------------
# 4. Centrality scores and deterministic rankings
# ---------------------------------------------------------------------------
def rank_scores(scores: Dict[int, float]) -> Dict[int, int]:
    """Rank by full-precision score descending, then Node_ID ascending."""
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return {node_id: rank for rank, (node_id, _score) in enumerate(ordered, start=1)}


def calculate_centralities(graph: nx.Graph) -> Tuple[pd.DataFrame, Dict[str, Dict[int, float]]]:
    print("\nCalculating centrality scores...")

    degree_counts = dict(graph.degree())
    degree_scores = nx.degree_centrality(graph)

    print("  [1/3] Degree centrality completed.")

    # Exact Brandes betweenness: k=None means all source nodes are used.
    betweenness_scores = nx.betweenness_centrality(
        graph,
        k=None,
        normalized=True,
        weight=None,
        endpoints=False,
    )
    print("  [2/3] Exact betweenness centrality completed.")

    pagerank_scores = nx.pagerank(
        graph,
        alpha=PAGERANK_ALPHA,
        tol=PAGERANK_TOL,
        max_iter=PAGERANK_MAX_ITER,
        weight=None,
    )
    print("  [3/3] PageRank completed.")

    degree_ranks = rank_scores(degree_scores)
    betweenness_ranks = rank_scores(betweenness_scores)
    pagerank_ranks = rank_scores(pagerank_scores)

    rows = []
    for node_id in sorted(graph.nodes()):
        rows.append(
            {
                "Node_ID": int(node_id),
                "Degree_Count": int(degree_counts[node_id]),
                "Degree": float(degree_scores[node_id]),
                "Degree_Rank": int(degree_ranks[node_id]),
                "Betweenness": float(betweenness_scores[node_id]),
                "Betweenness_Rank": int(betweenness_ranks[node_id]),
                "PageRank": float(pagerank_scores[node_id]),
                "PageRank_Rank": int(pagerank_ranks[node_id]),
            }
        )

    centrality_df = pd.DataFrame(rows)
    scores = {
        "Degree": degree_scores,
        "Betweenness": betweenness_scores,
        "PageRank": pagerank_scores,
    }
    return centrality_df, scores


def save_centrality_scores(centrality_df: pd.DataFrame, output_path: Path) -> None:
    centrality_df.to_csv(output_path, index=False, float_format="%.17g")
    print(f"Saved centrality scores: {output_path}")


def get_top_nodes(scores: Dict[int, float], k: int = TOP_K) -> List[Tuple[int, float]]:
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]


def print_top20_and_overlaps(scores: Dict[str, Dict[int, float]]) -> Dict[str, List[Tuple[int, float]]]:
    top = {name: get_top_nodes(values) for name, values in scores.items()}

    print("\n================ TOP-20 CENTRALITY NODES ================")
    for metric, entries in top.items():
        print(f"\n{metric} Top-{TOP_K} (Rank, Node_ID, Score):")
        for rank, (node_id, score) in enumerate(entries, start=1):
            print(f"{rank:>2}. Node {node_id:<5} Score = {score:.12g}")

    top_sets = {metric: {node for node, _ in entries} for metric, entries in top.items()}
    pairs = [
        ("Degree", "Betweenness"),
        ("Degree", "PageRank"),
        ("Betweenness", "PageRank"),
    ]
    print("\n================ TOP-20 OVERLAP ================")
    for a, b in pairs:
        overlap = sorted(top_sets[a] & top_sets[b])
        print(f"{a} ∩ {b}: {len(overlap)} nodes -> {overlap}")
    triple = sorted(top_sets["Degree"] & top_sets["Betweenness"] & top_sets["PageRank"])
    print(f"All three: {len(triple)} nodes -> {triple}")

    return top


# ---------------------------------------------------------------------------
# 5. Figures
# ---------------------------------------------------------------------------
def save_network_overview(graph: nx.Graph, output_path: Path) -> None:
    print("\nCreating network overview layout (this may take a little while)...")
    positions = nx.spring_layout(graph, seed=LAYOUT_SEED, iterations=30)

    fig, ax = plt.subplots(figsize=(12, 10))
    nx.draw_networkx_edges(graph, positions, ax=ax, width=0.25, alpha=0.08)
    nx.draw_networkx_nodes(graph, positions, ax=ax, node_size=5, linewidths=0)
    ax.set_title("SNAP Facebook Combined Network", fontsize=15)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {output_path}")


def save_degree_distribution(graph: nx.Graph, output_path: Path) -> None:
    degree_values = [degree for _node, degree in graph.degree()]
    fig, ax = plt.subplots(figsize=(9, 6))
    bins = np.arange(0, max(degree_values) + 2) - 0.5
    ax.hist(degree_values, bins=bins, edgecolor="black", linewidth=0.4)
    ax.set_yscale("log")
    ax.set_xlabel("Node degree")
    ax.set_ylabel("Number of nodes (log scale)")
    ax.set_title("Degree Distribution")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {output_path}")


def save_top20_bar_chart(
    metric_name: str,
    scores: Dict[int, float],
    output_path: Path,
) -> None:
    top_entries = get_top_nodes(scores, TOP_K)
    node_ids = [str(node_id) for node_id, _score in top_entries]
    values = [score for _node_id, score in top_entries]

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(node_ids, values)
    ax.invert_yaxis()
    ax.set_xlabel(f"{metric_name} score")
    ax.set_ylabel("Node ID (ranked from top to bottom)")
    ax.set_title(f"Top-{TOP_K} Nodes by {metric_name}")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {output_path}")


def save_rank_comparison(
    centrality_df: pd.DataFrame, output_path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.scatter(
        centrality_df["Betweenness_Rank"],
        centrality_df["PageRank_Rank"],
        s=10,
        alpha=0.45,
    )
    ax.set_xlabel("Betweenness rank (1 = highest)")
    ax.set_ylabel("PageRank rank (1 = highest)")
    ax.set_title("Betweenness Rank vs PageRank Rank")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {output_path}")


def save_top20_overlap_chart(
    scores: Dict[str, Dict[int, float]], output_path: Path
) -> None:
    top_sets = {
        metric: {node for node, _score in get_top_nodes(values, TOP_K)}
        for metric, values in scores.items()
    }
    labels = [
        "Degree &\nBetweenness",
        "Degree &\nPageRank",
        "Betweenness &\nPageRank",
    ]
    counts = [
        len(top_sets["Degree"] & top_sets["Betweenness"]),
        len(top_sets["Degree"] & top_sets["PageRank"]),
        len(top_sets["Betweenness"] & top_sets["PageRank"]),
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, counts)
    ax.set_ylabel("Number of shared nodes")
    ax.set_title(f"Pairwise Overlap Among Centrality Top-{TOP_K} Sets")
    ax.set_ylim(0, TOP_K)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {output_path}")


def create_all_figures(
    graph: nx.Graph,
    centrality_df: pd.DataFrame,
    scores: Dict[str, Dict[int, float]],
) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    save_network_overview(graph, FIGURE_DIR / "network_overview.png")
    save_degree_distribution(graph, FIGURE_DIR / "degree_distribution.png")
    save_top20_bar_chart("Degree", scores["Degree"], FIGURE_DIR / "top20_degree.png")
    save_top20_bar_chart(
        "Betweenness", scores["Betweenness"], FIGURE_DIR / "top20_betweenness.png"
    )
    save_top20_bar_chart("PageRank", scores["PageRank"], FIGURE_DIR / "top20_pagerank.png")
    save_rank_comparison(centrality_df, FIGURE_DIR / "centrality_rank_comparison.png")
    save_top20_overlap_chart(scores, FIGURE_DIR / "top20_overlap.png")


# ---------------------------------------------------------------------------
# 6. Generate a report draft from the actual computed outputs
# ---------------------------------------------------------------------------
def write_report(
    stats: Dict[str, float | int],
    top: Dict[str, List[Tuple[int, float]]],
    scores: Dict[str, Dict[int, float]],
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    top_sets = {metric: {node for node, _score in entries} for metric, entries in top.items()}
    overlap_pairs = [
        ("Degree", "Betweenness"),
        ("Degree", "PageRank"),
        ("Betweenness", "PageRank"),
    ]

    lines: List[str] = [
        "# A. Network Construction and Centrality Analysis",
        "",
        "## 1. Data Description",
        "",
        "This analysis uses the SNAP Facebook Social Circles combined edge list, "
        "`facebook_combined.txt.gz`. The dataset is an anonymized Facebook ego-network "
        "collection combined into one undirected network.",
        "",
        "Dataset reference: J. McAuley and J. Leskovec (2012), "
        "'Learning to Discover Social Circles in Ego Networks,' NeurIPS.",
        "",
        "## 2. Network Construction",
        "",
        "The input edge list was read as integer node IDs. The graph was constructed as "
        "an undirected, unweighted simple graph. Self-loops were removed, duplicate "
        "undirected edges (including reversed duplicates) were removed, and each output "
        "edge was stored in canonical `(min(Source, Target), max(Source, Target))` order.",
        "",
        "## 3. Network Statistics",
        "",
        "| Metric | Result |",
        "|---|---:|",
    ]

    stat_labels = [
        ("Nodes", "Nodes"),
        ("Edges", "Edges"),
        ("Density", "Density"),
        ("Average_Degree", "Average degree"),
        ("Average_Clustering_Coefficient", "Average clustering coefficient"),
        ("Connected_Components", "Number of connected components"),
        ("GCC_Nodes", "Nodes in GCC"),
        ("GCC_Fraction", "GCC fraction"),
        ("Average_Shortest_Path_GCC", "Average shortest path length on GCC"),
    ]
    for key, label in stat_labels:
        value = stats[key]
        formatted = f"{value:.10f}" if isinstance(value, float) else str(value)
        lines.append(f"| {label} | {formatted} |")

    lines.extend(
        [
            "",
            "The average shortest path length was calculated on the giant connected "
            "component (GCC), so that all node pairs used in this calculation are connected.",
            "",
            "## 4. Centrality Analysis",
            "",
            "Degree centrality was calculated as the node degree divided by `N - 1`. "
            "Betweenness centrality was calculated exactly (not sampled), normalized, "
            "with `endpoints=False` and `weight=None`. PageRank used damping factor "
            f"`{PAGERANK_ALPHA}`, tolerance `{PAGERANK_TOL}`, maximum iterations "
            f"`{PAGERANK_MAX_ITER}`, and `weight=None`.",
            "",
            "For all three measures, nodes were ranked by their full-precision score in "
            "descending order. Ties were resolved by ascending `Node_ID`; ranks start at 1.",
            "",
        ]
    )

    for metric in ["Degree", "Betweenness", "PageRank"]:
        lines.extend(
            [
                f"### {metric} Top-{TOP_K}",
                "",
                "| Rank | Node_ID | Score |",
                "|---:|---:|---:|",
            ]
        )
        for rank, (node_id, score) in enumerate(top[metric], start=1):
            lines.append(f"| {rank} | {node_id} | {score:.12g} |")
        lines.append("")

    lines.extend(["## 5. Top-20 Ranking Overlap", ""])
    for a, b in overlap_pairs:
        common = sorted(top_sets[a] & top_sets[b])
        lines.append(
            f"- **{a} and {b}:** {len(common)} shared nodes "
            f"({', '.join(map(str, common)) if common else 'none'})."
        )
    common_all = sorted(
        top_sets["Degree"] & top_sets["Betweenness"] & top_sets["PageRank"]
    )
    lines.append(
        f"- **All three measures:** {len(common_all)} shared nodes "
        f"({', '.join(map(str, common_all)) if common_all else 'none'})."
    )
    lines.extend(
        [
            "",
            "## 6. Interpretation (Complete After Reviewing the Figures)",
            "",
            "Discuss whether the same nodes are important under Degree, Betweenness, "
            "and PageRank. In particular, explain what the overlap and differences "
            "suggest about highly connected nodes, bridge-like nodes, and nodes connected "
            "to other influential nodes. Avoid claiming that these structural measures "
            "prove real-world information diffusion; diffusion experiments are handled "
            "by the relevant project members.",
            "",
            "## 7. Figures",
            "",
            "The generated figures are saved in `network_figures/`: `network_overview.png`, "
            "`degree_distribution.png`, `top20_degree.png`, `top20_betweenness.png`, "
            "`top20_pagerank.png`, `centrality_rank_comparison.png`, and `top20_overlap.png`.",
            "",
        ]
    )

    report_path = REPORT_DIR / "A_network_centrality.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved report draft: {report_path}")


# ---------------------------------------------------------------------------
# 7. Main workflow
# ---------------------------------------------------------------------------
def main() -> None:
    start_time = time.time()
    print("=" * 68)
    print("DSC6026 Final Project - Member A")
    print("Network Construction & Centrality Analysis")
    print("=" * 68)
    print(f"Python version : {sys.version.split()[0]}")
    print(f"NetworkX       : {nx.__version__}")
    print(f"NumPy          : {np.__version__}")
    print(f"Pandas         : {pd.__version__}")
    print(f"Dataset path   : {DATA_PATH}")

    # Read and clean raw data.
    print("\n[1/6] Reading and cleaning raw Facebook data...")
    edges, nodes, cleaning_info = read_and_clean_edges(DATA_PATH)
    print(f"  Unique nodes found : {len(nodes):,}")
    print(f"  Unique edges found : {len(edges):,}")
    print(f"  Cleaning summary   : {cleaning_info}")

    # Validate against the official SNAP combined dataset dimensions.
    if len(nodes) != EXPECTED_NODES or len(edges) != EXPECTED_EDGES:
        raise ValueError(
            "Dataset size does not match the expected SNAP facebook_combined dataset.\n"
            f"Expected: {EXPECTED_NODES:,} nodes and {EXPECTED_EDGES:,} edges.\n"
            f"Found:    {len(nodes):,} nodes and {len(edges):,} edges.\n"
            "Please check that you downloaded facebook_combined.txt.gz, not facebook.tar.gz "
            "or another Facebook dataset."
        )

    # Build graph and save the shared edge list.
    print("\n[2/6] Building the undirected, unweighted simple graph...")
    graph = build_graph(edges, nodes)
    print(
        f"  Graph ready: {graph.number_of_nodes():,} nodes, "
        f"{graph.number_of_edges():,} edges"
    )
    save_edge_table(edges, BASE_DIR / "facebook_edges.csv")

    # Calculate and save network statistics.
    print("\n[3/6] Calculating network statistics...")
    stats, gcc, components = calculate_network_statistics(graph, cleaning_info)
    save_network_statistics(stats, BASE_DIR / "network_stats.csv")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.12g}")
        else:
            print(f"  {key}: {value}")

    # Calculate all centralities exactly as specified.
    print("\n[4/6] Calculating centrality scores and rankings...")
    centrality_df, scores = calculate_centralities(graph)
    save_centrality_scores(centrality_df, BASE_DIR / "centrality_scores.csv")
    top = print_top20_and_overlaps(scores)

    # Create plots and report draft.
    print("\n[5/6] Creating figures...")
    create_all_figures(graph, centrality_df, scores)

    print("\n[6/6] Writing A report draft...")
    write_report(stats, top, scores)

    elapsed = time.time() - start_time
    print("\n" + "=" * 68)
    print("A PART COMPLETED")
    print(f"Total runtime: {elapsed / 60:.2f} minutes")
    print("Generated deliverables:")
    print("  facebook_edges.csv")
    print("  network_stats.csv")
    print("  centrality_scores.csv")
    print("  network_figures/")
    print("  report/A_network_centrality.md")
    print("=" * 68)


if __name__ == "__main__":
    main()
