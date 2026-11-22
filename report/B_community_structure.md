# Community structure and bridge nodes

Following the team protocol, Member B used Member A's `facebook_edges.csv` and `centrality_scores.csv` as the two inputs. The shared graph has 4,039 nodes and 88,234 undirected, unweighted friendship edges from the combined SNAP Facebook ego network. [Team protocol](../Final_Experiment_Protocol.md) · [SNAP dataset](https://snap.stanford.edu/data/ego-Facebook.html)

## Louvain communities

NetworkX 3.3 used `weight=None`, `resolution=1`, `threshold=1e-7`, and `seed=602610`. Louvain identified **16 communities** with modularity **0.834967**. Community sizes in decreasing order were 548, 535, 435, 430, 423, 350, 323, 237, 226, 206, 130, 73, 60, 25, 19, and 19. Of the observed edges, 84,787 (96.09%) lie within a community. [Group size figure](../community_figures/partition_sizes.pdf) · [Louvain method](https://doi.org/10.1088/1742-5468/2008/10/P10008)

## Degree-corrected stochastic block model

We fit a single-level, undirected `BlockState(deg_corr=True)` using **graph-tool 3.9** on one CPU thread. We seeded graph-tool and NumPy before each call to `minimize_blockmodel_dl` and compared the values returned by `state.entropy()`. Ties in the full-precision description length are resolved by selecting the smaller seed. [Degree correction](https://doi.org/10.1103/PhysRevE.83.016107) · [Inference method](https://doi.org/10.1103/PhysRevE.89.012804)

| Seed | Description length (nats) | Occupied blocks |
|---:|---:|---:|
| **602620** | **206,159.844704** | **60** |
| 602621 | 206,343.629313 | 60 |
| 602622 | 206,927.475298 | 62 |
| 602623 | 206,554.942513 | 64 |
| 602624 | 207,065.559191 | 61 |

The selected blocks range from 1 to 206 nodes and include three singletons. Seventeen blocks induce disconnected subgraphs. A structural block can group nodes with similar connection patterns.

For distinct blocks of sizes $n_r$ and $n_s$, density is the observed edge count divided by $n_r n_s$. The diagonal denominator is $n_r(n_r-1)/2$. Each undirected edge is counted once. The matrix is symmetric with a blank diagonal entry for each singleton. Of 1,770 distinct off-diagonal block pairs, 1,433 (81.0%) contain no edges. The 56,952 within-block edges account for 64.55% of the network. [Density matrix](../block_connectivity_matrix.csv) · [Density heatmap](../community_figures/block_connectivity_heatmap.pdf)

## Agreement between the partitions

The adjusted Rand index on all matched node IDs was **0.373559**. The largest Louvain community spans eight SBM blocks. Its two largest intersections contain 143 and 136 nodes. Each of Louvain communities 12 through 16 lies within a single SBM block. Louvain provides a coarser view of where edges concentrate, while the SBM resolves finer connection patterns within many of the larger communities. [Membership overlap](../community_figures/partition_overlap.pdf) · [Adjusted Rand index](https://doi.org/10.1007/BF01908075)

## Bridge profiles of the highest-ranked nodes

For each node, a crossing share is the number of incident edges reaching a different group divided by its degree. The table reports unweighted means across nodes. Ten nodes appear in both Top-20 lists and contribute to both full-list means. [Per-node results](../bridge_analysis.csv) · [Bridge profile figure](../community_figures/top20_bridging.pdf)

| Node set | Nodes | Cross-community share | Cross-community count | Cross-block share | Cross-block count |
|---|---:|---:|---:|---:|---:|
| PageRank Top-20 | 20 | 10.36% | 66.75 | 57.56% | 225.95 |
| Betweenness Top-20 | 20 | 22.46% | 71.05 | 68.95% | 225.00 |
| PageRank only | 10 | 4.43% | 9.00 | 45.56% | 70.70 |
| Betweenness only | 10 | 28.62% | 17.60 | 68.35% | 68.80 |
| Both lists | 10 | 16.29% | 124.50 | 69.55% | 381.20 |
| All nodes | 4,039 | 4.16% | 1.71 | 30.19% | 15.49 |

The betweenness Top-20 had larger crossing shares at both resolutions and more distinct external blocks per node on average (8.60 versus 7.10). Both rankings occupied eight Louvain communities. The betweenness Top-20 occupied 16 SBM blocks and the PageRank Top-20 occupied 14. The mean absolute number of cross-block edges was nearly equal across rankings. PageRank-only nodes had higher mean degree (117.3 versus 81.5), while betweenness-only nodes assigned a larger fraction of their ties to external groups.

Shared node 107 ranked first by betweenness and second by PageRank. Of its 1,045 edges, 611 leave its Louvain community and all leave its singleton SBM block. Its high cross-community count provides additional evidence of bridging under the coarser partition. These patterns give the diffusion and removal analyses a way to interpret potential routes. Realized simulated spread also depends on propagation probabilities, seeds, and alternate routes. The graph captures anonymized friendships at a single point in time.

## Reproducing the outputs

Run these commands from the repository root. The recorded execution used macOS on Apple Silicon.

```bash
conda create -n dsc6026-b --override-channels -c conda-forge \
  python=3.12.7 numpy=1.26.4 scipy=1.16.3 networkx=3.3 \
  graph-tool-base=3.9 matplotlib-base=3.11.2
conda run -n dsc6026-b python community_analysis.py
```

Place Member A's `facebook_edges.csv` and `centrality_scores.csv` beside the script. It writes results to the repository root by default. Use `--output-dir` to write to a separate directory. All CSV files are UTF-8. Node IDs are original integers. Community and block IDs start at 1 and are ordered by size, with equal sizes ordered by smallest node ID. The bridge CSV contains one row per distinct node from either Top-20 list and separate membership flags. Exact run statistics and library versions are in the [analysis summary](../community_analysis_summary.json).

Insert the [section source](B_community_structure.tex) after Section 1 in the group report. Include the [four figures](../community_figures/) and merge the [BibTeX entries](B_references.bib) into the group's bibliography. The [preview main file](B_main.tex) compiles the section on its own with the [NeurIPS 2025 style](neurips_2025.sty) and author–year citations via `natbib` and `plainnat`.
