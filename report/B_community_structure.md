# B. Community Detection and Structural Analysis

Louvain identified 16 communities, and the degree-corrected stochastic block model (SBM) identified 60 structural blocks. The betweenness Top-20 had a higher mean share of ties across both partitions than the PageRank Top-20. Their mean counts of cross-block ties were close.

## 1. Data and Analysis Setup

We used the canonical edge table and centrality rankings published by Member A. The graph contains 4,039 nodes and 88,234 undirected, unweighted friendship edges from the combined SNAP Facebook ego network. Original integer node IDs and the two original-graph Top-20 rankings were preserved. [Member A's report](A_network_centrality.md) · [Edge table](../facebook_edges.csv) · [Centrality rankings](../centrality_scores.csv) · [Final experiment protocol](../Final_Experiment_Protocol.md)

## 2. Louvain Community Detection

We ran Louvain in NetworkX 3.3 with `weight=None`, `resolution=1`, `threshold=1e-7`, and `seed=602610`. [Louvain method](https://doi.org/10.1088/1742-5468/2008/10/P10008)

| Metric | Result |
|---|---:|
| Louvain communities | 16 |
| Modularity | 0.834967 |
| Smallest and largest communities | 19 and 548 nodes |
| Within-community edges | 84,787 (96.09%) |

The community sizes in descending order were 548, 535, 435, 430, 423, 350, 323, 237, 226, 206, 130, 73, 60, 25, 19, and 19. [Community labels][community-labels] · [Group sizes][figure-sizes]

## 3. Degree-Corrected Stochastic Block Model

We fit a single-level, undirected, unweighted `BlockState(deg_corr=True)` using graph-tool 3.9 on one CPU thread. We seeded graph-tool and NumPy for each call to `minimize_blockmodel_dl`, then selected the smallest full-precision description length from `state.entropy()`. An exact tie would be resolved by the smaller seed. [Degree correction](https://doi.org/10.1103/PhysRevE.83.016107) · [Inference method](https://doi.org/10.1103/PhysRevE.89.012804)

| Seed | Description length (nats) | Occupied blocks |
|---:|---:|---:|
| **602620** | **206,159.844704** | **60** |
| 602621 | 206,343.629313 | 60 |
| 602622 | 206,927.475298 | 62 |
| 602623 | 206,554.942513 | 64 |
| 602624 | 207,065.559191 | 61 |

The selected blocks ranged from 1 to 206 nodes, including three singletons. Seventeen blocks induced disconnected subgraphs. A structural block can group nodes with similar connection patterns. [Block labels][block-labels]

Across two blocks of sizes $n_r$ and $n_s$, density was the observed edge count divided by $n_r n_s$. Within a block, the denominator was $n_r(n_r-1)/2$. Each undirected edge was counted once. A blank singleton diagonal indicates an undefined density. Of 1,770 distinct off-diagonal block pairs, 1,433 (81.0%) contained no edges. Within-block edges accounted for 56,952 edges (64.55%). [Density matrix][density-matrix] · [Density heatmap][figure-density]

## 4. Agreement between the Partitions

The adjusted Rand index across all 4,039 matched node IDs was **0.373559**. The largest Louvain community spans eight SBM blocks, and its two largest intersections contain 143 and 136 nodes. Louvain communities 12 through 16 each lie within one SBM block. These patterns show agreement on some local groups and finer subdivisions of several large communities in the SBM. [Membership overlap][figure-overlap] · [Adjusted Rand index](https://doi.org/10.1007/BF01908075)

## 5. Bridge Profiles of the Top-20 Nodes

For each node, the crossing share is the number of incident edges reaching a different community or block divided by its degree. The table reports means with equal weight per node. The ten nodes shared by the two full Top-20 lists contribute to both full-list means. [Per-node results][bridge-results]

| Node set | Nodes | Cross-community share | Cross-community count | Cross-block share | Cross-block count |
|---|---:|---:|---:|---:|---:|
| PageRank Top-20 | 20 | 10.36% | 66.75 | 57.56% | 225.95 |
| Betweenness Top-20 | 20 | 22.46% | 71.05 | 68.95% | 225.00 |
| PageRank only | 10 | 4.43% | 9.00 | 45.56% | 70.70 |
| Betweenness only | 10 | 28.62% | 17.60 | 68.35% | 68.80 |
| Both lists | 10 | 16.29% | 124.50 | 69.55% | 381.20 |
| All nodes | 4,039 | 4.16% | 1.71 | 30.19% | 15.49 |

Both rankings covered eight Louvain communities. Betweenness covered 16 SBM blocks and PageRank covered 14. Betweenness Top-20 nodes reached 8.60 distinct external blocks on average, compared with 7.10 for PageRank. In the disjoint subsets, PageRank-only nodes had a higher mean degree (117.3 versus 81.5). Betweenness-only nodes had higher shares of ties crossing both communities and blocks. [Bridge profiles][figure-bridges]

## 6. Interpretation

Node 107 ranked first by betweenness and second by PageRank. Of its 1,045 edges, 611 crossed its Louvain community boundary. All 1,045 crossed block boundaries because its SBM block was a singleton. Its Louvain crossing count gives evidence of bridging under the coarser partition.

The two rankings differed more in the share of a node's ties reaching another block than in the absolute count of those ties. These structural results describe potential diffusion routes on one friendship graph. Simulated reach depends on the seed set, propagation probability, and alternate routes. At the primary probability of `p = 0.05`, the paired diffusion comparison found a small difference with a confidence interval spanning zero. [Seed selection and diffusion results](C_seed_diffusion.md)

## 7. Figures and Reproduction

- [Figure 1. Louvain community and SBM block sizes][figure-sizes]
- [Figure 2. SBM block-pair density heatmap][figure-density]
- [Figure 3. Membership overlap between Louvain and SBM][figure-overlap]
- [Figure 4. Per-node bridge profiles for the two Top-20 rankings][figure-bridges]

Run these commands from the root of the [analysis branch][analysis-branch]. The recorded execution used macOS on Apple Silicon.

```bash
conda create -n dsc6026-b --override-channels -c conda-forge \
  python=3.12.7 numpy=1.26.4 scipy=1.16.3 networkx=3.3 \
  graph-tool-base=3.9 matplotlib-base=3.11.2
conda run -n dsc6026-b python community_analysis.py
```

Community and block IDs start at 1 and are ordered by size, with equal sizes ordered by smallest node ID. The bridge CSV contains one row for each of the 30 distinct nodes from the two Top-20 lists and separate membership flags. [Analysis script][analysis-script] · [Full run summary][analysis-summary] · [LaTeX section][latex-section] · [BibTeX references][references]

[analysis-branch]: https://github.com/jme199/DSC6026-Final-Project/tree/task-b-community-structure
[analysis-script]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_analysis.py
[analysis-summary]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_analysis_summary.json
[community-labels]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/louvain_communities.csv
[block-labels]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/sbm_block_labels.csv
[density-matrix]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/block_connectivity_matrix.csv
[bridge-results]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/bridge_analysis.csv
[figure-sizes]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_figures/partition_sizes.pdf
[figure-density]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_figures/block_connectivity_heatmap.pdf
[figure-overlap]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_figures/partition_overlap.pdf
[figure-bridges]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/community_figures/top20_bridging.pdf
[latex-section]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/report/B_community_structure.tex
[references]: https://github.com/jme199/DSC6026-Final-Project/blob/task-b-community-structure/report/B_references.bib
