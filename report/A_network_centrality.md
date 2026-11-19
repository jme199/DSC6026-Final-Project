# A. Network Construction and Centrality Analysis

## 1. Data Description

This analysis uses the SNAP Facebook Social Circles combined edge list, `facebook_combined.txt.gz`. The dataset is an anonymized Facebook ego-network collection combined into one undirected network.

Dataset reference: J. McAuley and J. Leskovec (2012), 'Learning to Discover Social Circles in Ego Networks,' NeurIPS.

## 2. Network Construction

The input edge list was read as integer node IDs. The graph was constructed as an undirected, unweighted simple graph. Self-loops were removed, duplicate undirected edges (including reversed duplicates) were removed, and each output edge was stored in canonical `(min(Source, Target), max(Source, Target))` order.

## 3. Network Statistics

| Metric | Result |
|---|---:|
| Nodes | 4039 |
| Edges | 88234 |
| Density | 0.0108199635 |
| Average degree | 43.6910126269 |
| Average clustering coefficient | 0.6055467186 |
| Number of connected components | 1 |
| Nodes in GCC | 4039 |
| GCC fraction | 1.0000000000 |
| Average shortest path length on GCC | 3.6925068497 |

The average shortest path length was calculated on the giant connected component (GCC), so that all node pairs used in this calculation are connected.

## 4. Centrality Analysis

Degree centrality was calculated as the node degree divided by `N - 1`. Betweenness centrality was calculated exactly (not sampled), normalized, with `endpoints=False` and `weight=None`. PageRank used damping factor `0.85`, tolerance `1e-08`, maximum iterations `1000`, and `weight=None`.

For all three measures, nodes were ranked by their full-precision score in descending order. Ties were resolved by ascending `Node_ID`; ranks start at 1.

### Degree Top-20

| Rank | Node_ID | Score |
|---:|---:|---:|
| 1 | 107 | 0.258791480931 |
| 2 | 1684 | 0.196136701337 |
| 3 | 1912 | 0.186973749381 |
| 4 | 3437 | 0.135463100545 |
| 5 | 0 | 0.0859336305102 |
| 6 | 2543 | 0.072808320951 |
| 7 | 2347 | 0.0720653789004 |
| 8 | 1888 | 0.062902426944 |
| 9 | 1800 | 0.0606736007925 |
| 10 | 1663 | 0.0581971272907 |
| 11 | 1352 | 0.0579494799406 |
| 12 | 2266 | 0.0579494799406 |
| 13 | 483 | 0.05720653789 |
| 14 | 348 | 0.0567112431897 |
| 15 | 1730 | 0.0559683011392 |
| 16 | 1985 | 0.0554730064388 |
| 17 | 1941 | 0.0552253590887 |
| 18 | 2233 | 0.0549777117385 |
| 19 | 2142 | 0.0547300643883 |
| 20 | 1431 | 0.0544824170381 |

### Betweenness Top-20

| Rank | Node_ID | Score |
|---:|---:|---:|
| 1 | 107 | 0.480518078556 |
| 2 | 1684 | 0.33779744973 |
| 3 | 3437 | 0.236115357359 |
| 4 | 1912 | 0.229295339587 |
| 5 | 1085 | 0.149015092117 |
| 6 | 0 | 0.146305921474 |
| 7 | 698 | 0.115330450206 |
| 8 | 567 | 0.0963103312186 |
| 9 | 58 | 0.084360205908 |
| 10 | 428 | 0.0643090623932 |
| 11 | 563 | 0.0627802284724 |
| 12 | 860 | 0.0578259068709 |
| 13 | 414 | 0.0476333729717 |
| 14 | 1577 | 0.0397847050294 |
| 15 | 348 | 0.0379980974809 |
| 16 | 1718 | 0.037342870678 |
| 17 | 686 | 0.0297218983751 |
| 18 | 594 | 0.0288031981635 |
| 19 | 136 | 0.0268703597874 |
| 20 | 3980 | 0.0248200336362 |

### PageRank Top-20

| Rank | Node_ID | Score |
|---:|---:|---:|
| 1 | 3437 | 0.00757509438259 |
| 2 | 107 | 0.0068882223704 |
| 3 | 1684 | 0.00630887123708 |
| 4 | 0 | 0.00622575189596 |
| 5 | 1912 | 0.00381690866871 |
| 6 | 348 | 0.00231787433206 |
| 7 | 686 | 0.002216786827 |
| 8 | 3980 | 0.00215692318083 |
| 9 | 414 | 0.0017827538721 |
| 10 | 483 | 0.00129440576742 |
| 11 | 698 | 0.00129207166712 |
| 12 | 3830 | 0.00118670332737 |
| 13 | 376 | 0.00089673015249 |
| 14 | 2047 | 0.000830641941342 |
| 15 | 56 | 0.000810175791627 |
| 16 | 25 | 0.00080407983514 |
| 17 | 828 | 0.000794430505757 |
| 18 | 322 | 0.00079123680075 |
| 19 | 475 | 0.000781064291664 |
| 20 | 67 | 0.000778447245968 |

## 5. Top-20 Ranking Overlap

- **Degree and Betweenness:** 6 shared nodes (0, 107, 348, 1684, 1912, 3437).
- **Degree and PageRank:** 7 shared nodes (0, 107, 348, 483, 1684, 1912, 3437).
- **Betweenness and PageRank:** 10 shared nodes (0, 107, 348, 414, 686, 698, 1684, 1912, 3437, 3980).
- **All three measures:** 6 shared nodes (0, 107, 348, 1684, 1912, 3437).

## 6. Interpretation (Complete After Reviewing the Figures)

Discuss whether the same nodes are important under Degree, Betweenness, and PageRank. In particular, explain what the overlap and differences suggest about highly connected nodes, bridge-like nodes, and nodes connected to other influential nodes. Avoid claiming that these structural measures prove real-world information diffusion; diffusion experiments are handled by the relevant project members.

## 7. Figures

The generated figures are saved in `network_figures/`: `network_overview.png`, `degree_distribution.png`, `top20_degree.png`, `top20_betweenness.png`, `top20_pagerank.png`, `centrality_rank_comparison.png`, and `top20_overlap.png`.
