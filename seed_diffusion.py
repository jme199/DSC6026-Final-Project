"""Run the project's formal RQ1 experiment and regenerate Member C outputs."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import networkx as nx
import numpy as np
from scipy.stats import t

from ic_core import PreparedIC


ROOT = Path(__file__).resolve().parent
NODE_COUNT = 4039
EDGE_COUNT = 88234
TOP_K = 20
TRIALS = 200
SEED_BASE = 602900
MAIN_P = 0.05
PROBABILITIES = (0.01, 0.02, MAIN_P, 0.10, 0.20)
STRATEGIES = ("PageRank", "Betweenness")
COLORS = ("#17649a", "#b54e14")

TRIAL_FIELDS = (
    "Trial_ID", "Probability_p", "Seed_Strategy", "Live_Edge_Seed",
    "Final_Activated", "Activated_Fraction", "Rounds", "Round_Counts",
)


def read_graph(path):
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as file:
            edges = [(int(row["Source"]), int(row["Target"])) for row in csv.DictReader(file)]
    else:
        edges = list(nx.read_edgelist(path, nodetype=int, data=False).edges())
    canonical = sorted((min(u, v), max(u, v)) for u, v in edges)
    graph = nx.Graph()
    graph.add_nodes_from(sorted({node for edge in canonical for node in edge}))
    graph.add_edges_from(canonical)
    if (
        len(graph) != NODE_COUNT
        or graph.number_of_edges() != EDGE_COUNT
        or len(edges) != EDGE_COUNT
        or nx.number_of_selfloops(graph)
    ):
        raise ValueError(f"Expected the simple SNAP Facebook graph in {path}")
    return graph


def read_seeds(path, graph):
    with path.open(newline="", encoding="utf-8-sig") as file:
        scores = list(csv.DictReader(file))
    if len(scores) != len(graph) or {int(row["Node_ID"]) for row in scores} != set(graph):
        raise ValueError(f"Centrality rows must contain each graph node exactly once: {path}")
    selections = {}
    for strategy in STRATEGIES:
        ranked = sorted(scores, key=lambda row: int(row[f"{strategy}_Rank"]))
        if any(int(row[f"{strategy}_Rank"]) != i for i, row in enumerate(ranked, start=1)):
            raise ValueError(f"{strategy} ranks must run from 1 through {len(graph)}")
        selections[strategy] = [int(row["Node_ID"]) for row in ranked[:TOP_K]]
    return selections


def simulate(graph, seed_sets, trial_path):
    topology = PreparedIC.from_graph(graph)
    by_p = {}
    with trial_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRIAL_FIELDS)
        writer.writeheader()
        for p in PROBABILITIES:
            batch = {strategy: [] for strategy in STRATEGIES}
            for trial_id in range(TRIALS):
                live_seed = SEED_BASE + trial_id
                arc_uniforms = topology.live_arcs(live_seed)
                for strategy in STRATEGIES:
                    result = topology.cascade(seed_sets[strategy], p, arc_uniforms)
                    batch[strategy].append(result)
                    writer.writerow({
                        "Trial_ID": trial_id,
                        "Probability_p": f"{p:.2f}",
                        "Seed_Strategy": strategy,
                        "Live_Edge_Seed": live_seed,
                        "Final_Activated": result["final_activated"],
                        "Activated_Fraction": result["activated_fraction"],
                        "Rounds": result["rounds"],
                        "Round_Counts": json.dumps(result["round_counts"]),
                    })
            file.flush()
            by_p[p] = batch
            print(f"p={p:.2f}: {TRIALS} pairs complete", flush=True)
    return by_p


def final_counts(results):
    return np.array([trial["final_activated"] for trial in results])


def summarize(results, path):
    summary = []
    for p, batch in results.items():
        counts = {strategy: final_counts(batch[strategy]) for strategy in STRATEGIES}
        differences = counts["PageRank"] - counts["Betweenness"]
        diff_mean = differences.mean()
        diff_sd = differences.std(ddof=1)
        halfwidth = t.ppf(0.975, TRIALS - 1) * diff_sd / np.sqrt(TRIALS)
        row = {"Probability_p": f"{p:.2f}", "Analysis": "Main" if p == MAIN_P else "Sensitivity",
               "Paired_Trials": TRIALS}
        for strategy in STRATEGIES:
            mean = counts[strategy].mean()
            row[f"{strategy}_Mean_Activated"] = mean
            row[f"{strategy}_SD_Activated"] = counts[strategy].std(ddof=1)
            row[f"{strategy}_Mean_Coverage_Pct"] = 100 * mean / NODE_COUNT
        row.update(Paired_Mean_Difference_Nodes=diff_mean,
                   Paired_SD_Difference_Nodes=diff_sd,
                   Paired_CI95_Lower_Nodes=diff_mean - halfwidth,
                   Paired_CI95_Upper_Nodes=diff_mean + halfwidth,
                   Paired_Mean_Difference_Coverage_PP=100 * diff_mean / NODE_COUNT)
        summary.append(row)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def make_figures(results, directory):
    directory.mkdir(exist_ok=True)
    box_figure, box_axes = plt.subplots(2, 3, figsize=(10.6, 6.5), layout="constrained")
    curve_figure, curve_axes = plt.subplots(2, 3, figsize=(10.6, 6.5), layout="constrained",
                                            sharey=True)
    box_figure.suptitle("Final network coverage by seed strategy", fontsize=16, fontweight="bold")
    curve_figure.suptitle("Mean cumulative reach by diffusion round", fontsize=16, fontweight="bold")
    for (p, batch), box, curve in zip(results.items(), box_axes.flat, curve_axes.flat):
        title = f"p = {p:.2f}" + ("  ·  Main" if p == MAIN_P else "")
        for axis in (box, curve):
            axis.set_title(title, loc="left", fontweight="bold" if p == MAIN_P else "normal")
            axis.grid(axis="y", alpha=0.25)
            axis.set_axisbelow(True)
            axis.spines[["top", "right"]].set_visible(False)
        coverage = [100 * final_counts(batch[strategy]) / NODE_COUNT for strategy in STRATEGIES]
        artists = box.boxplot(coverage, tick_labels=STRATEGIES, patch_artist=True, widths=0.48,
                              medianprops={"color": "#172838", "linewidth": 1.5},
                              flierprops={"markersize": 2.5, "alpha": 0.6})
        for patch, color in zip(artists["boxes"], COLORS):
            patch.set(facecolor=color, alpha=0.38, edgecolor=color, linewidth=1.5)
        box.set_ylabel("Final coverage (%)")

        last_round = max(trial["rounds"] for runs in batch.values() for trial in runs)
        for strategy, color, linestyle in zip(STRATEGIES, COLORS, ("-", "--")):
            cumulative = [
                np.pad(np.cumsum(trial["round_counts"]), (0, last_round - trial["rounds"]),
                       mode="edge")
                for trial in batch[strategy]
            ]
            curve.plot(np.arange(last_round + 1), 100 * np.mean(cumulative, axis=0) / NODE_COUNT,
                       label=strategy, color=color, linestyle=linestyle, linewidth=1.8)
        curve.set_ylim(0, 100)
        curve.set_xlabel("Round")
        curve.set_ylabel("Cumulative coverage (%)")
        curve.set_xlim(0, last_round)
        curve.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))

    box_note = box_axes.flat[-1]
    box_note.axis("off")
    box_note.text(0.05, 0.82, "200 paired trials per probability", weight="bold",
                  transform=box_note.transAxes)
    box_note.text(0.05, 0.57, "Boxes show the middle 50% of trials.\nVertical scales vary by panel.",
                  transform=box_note.transAxes, linespacing=1.5)
    legend = curve_axes.flat[-1]
    legend.axis("off")
    handles, labels = curve_axes.flat[0].get_legend_handles_labels()
    legend.legend(handles, labels, loc="upper left", frameon=False)
    legend.text(0.06, 0.51, "Each curve includes the 20 initial seeds.\nCompleted trials retain their\nfinal count at later rounds.",
                transform=legend.transAxes, linespacing=1.45)
    box_figure.savefig(directory / "seed_diffusion_boxplot.png", dpi=160, facecolor="white")
    curve_figure.savefig(directory / "seed_diffusion_curves.png", dpi=160, facecolor="white")
    plt.close(box_figure)
    plt.close(curve_figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edges", type=Path)
    parser.add_argument("--centrality", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    shared_edges = ROOT / "facebook_edges.csv"
    shared_scores = ROOT / "centrality_scores.csv"
    edge_path = args.edges or (shared_edges if shared_edges.exists()
                              else ROOT / "data/raw/facebook_combined.txt.gz")
    centrality_path = args.centrality or (shared_scores if shared_scores.exists()
                                         else ROOT / "pilot/centrality_scores.csv")
    graph = read_graph(edge_path)
    seeds = read_seeds(centrality_path, graph)
    print(f"Edges: {edge_path}\nCentrality: {centrality_path}")
    for strategy, nodes in seeds.items():
        print(f"{strategy} seeds: {nodes}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trial_csv = "seed_diffusion_trials.csv"
    summary_csv = "seed_diffusion_summary.csv"
    figure_dir = "diffusion_figures"
    with TemporaryDirectory(dir=args.output_dir, prefix=".seed-diffusion-") as temp:
        staging = Path(temp)
        results = simulate(graph, seeds, staging / trial_csv)
        summarize(results, staging / summary_csv)
        make_figures(results, staging / figure_dir)
        for filename in (trial_csv, summary_csv):
            (staging / filename).replace(args.output_dir / filename)
        destination = args.output_dir / figure_dir
        destination.mkdir(exist_ok=True)
        for figure in (staging / figure_dir).iterdir():
            figure.replace(destination / figure.name)


if __name__ == "__main__":
    main()
