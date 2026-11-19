# Seed Selection and Information Diffusion

RQ1 asks whether PageRank or betweenness centrality selects more effective seeds for information diffusion on the SNAP Facebook network. Under the primary setting of `p = 0.05`, the two strategies each reached about 55% of the network. The paired estimate was 1.85 additional activations for PageRank (95% CI −0.22 to 3.91 nodes), so the primary comparison did not establish a clear advantage for either strategy.

## Independent cascade and experimental design

The experiment was conducted on the original undirected, unweighted SNAP Facebook graph containing 4,039 nodes and 88,234 edges. For each strategy, the 20 highest-ranked nodes were activated at round 0. PageRank was calculated with damping 0.85 and tolerance `1e-8`. Betweenness was calculated exactly, with normalization and endpoint exclusion. Ties were resolved by ascending node ID. Ten nodes were shared between the two seed sets. The formal run was performed using the repository's raw edge list and published exact centrality rankings, as the shared root-level edge and centrality CSV files were unavailable at the time. [Raw edge list](../data/raw/facebook_combined.txt.gz) · [Published centrality rankings](../pilot/centrality_scores.csv) · [SNAP dataset](https://snap.stanford.edu/data/egonets-Facebook.html)

Following the upload of Member A's shared CSVs, the complete node and undirected edge sets were compared with the inputs used for this experiment. Exact agreement was confirmed for all 4,039 nodes and 88,234 edges. Both PageRank and betweenness Top-20 lists were verified to match in membership and order. Successful loading of Member A's files was also confirmed, with identical canonical directed-edge arrays and seed sets obtained. Consistency of the existing 2,000-cascade results with the shared inputs was therefore verified. [Member A's edge table](../facebook_edges.csv) · [Member A's centrality table](../centrality_scores.csv)

For each of 200 trials at every probability, one independent uniform draw was generated for each direction of every edge using PCG64 with seed `602900 + Trial_ID`. A direction was designated as available when its draw fell below `p`. Identical draws were applied to both seed strategies within each pair and reused across probabilities for the same trial ID. Reachable nodes and their first activation rounds were determined using the shared live-edge implementation. The initial seeds were included in coverage, and the original node count was used as the denominator. Across the five probabilities, 1,000 paired trials and 2,000 cascades were completed. [Final experiment protocol](../Final_Experiment_Protocol.md) · [IC implementation](../ic_core.py)

## Results

The table reports mean and sample SD in activated nodes. We calculated the two-sided 95% t interval from the 200 within-trial differences at each probability. Differences are PageRank minus betweenness. Intervals for the sensitivity settings are pointwise.

| Probability | PageRank, mean ± SD | Betweenness, mean ± SD | Paired mean difference | 95% CI, nodes |
|---:|---:|---:|---:|---:|
| 0.01 | 298.54 ± 76.30 | 300.85 ± 75.46 | −2.32 | [−8.39, 3.76] |
| 0.02 | 962.73 ± 63.27 | 944.70 ± 65.34 | +18.03 | [15.42, 20.64] |
| **0.05 (primary)** | **2,240.17 ± 43.90** | **2,238.33 ± 47.56** | **+1.85** | **[−0.22, 3.91]** |
| 0.10 | 3,057.45 ± 29.05 | 3,059.95 ± 29.21 | −2.50 | [−2.72, −2.27] |
| 0.20 | 3,603.87 ± 20.23 | 3,605.35 ± 20.24 | −1.49 | [−1.69, −1.28] |

At the primary probability, PageRank reached 55.46% of nodes and betweenness reached 55.42%, a difference of 0.046 percentage points. PageRank had its largest advantage at `p = 0.02`, with 18.03 additional nodes, equivalent to 0.446 percentage points of network coverage. At `p = 0.10` and `p = 0.20`, betweenness had a small advantage of fewer than three nodes on average. The change in direction across probabilities and the small differences in coverage show that the seed rankings do not have a consistent ordering across settings.

![Final coverage boxplots at all five probabilities](../diffusion_figures/seed_diffusion_boxplot.png)

*Figure 1. Final coverage by probability and seed strategy. The vertical scale varies by panel to show each distribution.*

![Mean cumulative coverage curves at all five probabilities](../diffusion_figures/seed_diffusion_curves.png)

*Figure 2. Mean cumulative coverage by round. Each completed cascade retains its final count in the average at subsequent rounds.*

The mean curves for the two strategies largely overlap. Higher probabilities produce faster growth and higher final coverage, from about 7.4% at `p = 0.01` to about 89.2% at `p = 0.20`. The intervals quantify Monte Carlo uncertainty for these fixed seed lists on one graph. They do not measure variation across other networks or observed Facebook sharing behavior.

Run `python seed_diffusion.py` from the repository root to reproduce the CSVs and figures. The run used Python 3.12.7, NetworkX 3.3, NumPy 1.26.4, SciPy 1.16.3, and Matplotlib 3.9.2. The script uses the shared CSV inputs when present and otherwise uses the published edge list and rankings above. [Analysis script](../seed_diffusion.py) · [Trial data](../seed_diffusion_trials.csv) · [Statistical summary](../seed_diffusion_summary.csv)
