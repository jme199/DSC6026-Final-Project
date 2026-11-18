# DSC6026 Final Group Project 实验协议

## 正式实验配置

项目使用 Stanford SNAP 的 Facebook 合并边表。图为无向、无权简单图，包含 4,039 个节点和 88,234 条边。保留原始整数节点 ID，去自环、去重，每条边按 `(min, max)` 存储并按字典序排列。正式实验的 A、B、C、D、E 模块共用 A 发布的边表与中心性排名。[SNAP 数据页](https://snap.stanford.edu/data/egonets-Facebook.html)

| 成员 | 正式配置 | 计算量 |
|---|---|---:|
| A | 描述统计、Degree、PageRank、精确 Betweenness | 单张原图 |
| B | Louvain 与 degree-corrected SBM | 单张原图 |
| C | PageRank Top-20 与 Betweenness Top-20 作为种子。每个 `p` 做 200 个配对试次 | 2,000 次 IC |
| D | 原图 1 次，两种定向移除各 1 次，随机移除 50 次。每次移除 20 个节点 | 53 次结构分析，含原图 |
| E | 原图、PageRank 移除、Betweenness 移除、随机移除。每个 `p` 做 200 个配对试次 | 4,000 次 IC |

- C、E 主分析 `p=0.05`，敏感性分析 `p ∈ {0.01, 0.02, 0.10, 0.20}`。每个 `p` 使用 `Trial_ID=0…199`，统一固定 200 次。
- 使用 CPU，并在计时实验所属的 Python 3.12.7、NumPy 1.26.4、SciPy 1.16.3、NetworkX 3.3 环境复现 A、C、D、E 及 B 的 Louvain。相同试次复用随机边数组，每完成一个概率批次保存原始记录。

## A 与 B 的方法参数

- A 输出节点数、边数、密度、平均度、平均局部聚类系数、连通分量数和 GCC 平均最短路径。CSV 的 `Degree` 保存度数，标准化 Degree Centrality 为 `Degree/(N−1)`。PageRank 设 `alpha=0.85, tol=1e-8, max_iter=1000, weight=None`。Betweenness 用全节点精确算法，`normalized=True, weight=None, endpoints=False`。按全精度分数降序，同分按整数节点 ID 升序，排名从 1 开始。两组 Top-20 在原图一次性确定。
- Louvain 使用 `weight=None, resolution=1, threshold=1e-7, seed=602610`，记录模块度、社区数和规模。SBM 用单层、无权、无向的 degree-corrected `BlockState`，`deg_corr=True`。以 `602620…602624` 初始化 5 次 `minimize_blockmodel_dl`，保留最小描述长度 `state.entropy()` 的一组，近似相等时按实际描述长度比较，完全相同取较小种子。保存 graph-tool 版本、各次描述长度、块数、节点标签及块间密度。跨块密度分母为两块节点数乘积，块内用可能的无向边数。B 的 SBM 配置是正式选定的运行参数，本机缺少 graph-tool，尚无 SBM 试跑或实测耗时。 [graph-tool 推断函数](https://graph-tool.skewed.de/static/docs/stable/autosummary/graph_tool.inference.minimize_blockmodel_dl.html) · [BlockState 参数](https://graph-tool.skewed.de/static/docs/stable/autosummary/graph_tool.inference.BlockState.html)

## C、D、E 的配对规则

- 公共接口为 [ic_core.py](ic_core.py) 中的 `simulate_ic(G, seeds, p, live_edge_seed, removed_nodes=None)`。批量运行时将原图预处理为 `PreparedIC`，按有向 `(source ID, target ID)` 排序。每条无向边的两个方向分别用 PCG64 抽取 (U)，当 `U < p` 时为有效传播方向。移除节点时屏蔽相关方向，并保留其余方向的随机值。第 0 轮激活全部种子，按多源 BFS 的距离返回每轮新增数，直到无新增活跃节点。覆盖率固定除以原图 4,039 个节点，`rounds` 为最后一个有新增节点的轮次。
- C 对两组固定种子共享 `live_edge_seed=602900+r`。报告 `PageRank − Betweenness` 的配对最终激活数差值。
- D、E 通过同一 `intervention_nodes` 规则生成第 `r` 次的节点集合。用 `default_rng(602600+r)` 从排好序的 `V − (P20∪B20)` 无放回抽 20 个传播种子 `S_r`。用 `default_rng(602700+r)` 从排好序的 `V − S_r` 无放回抽 20 个随机移除节点。D 只执行 `r=0…49`，与 E 的前 50 组移除完全对应。
- E 在同一 `r` 的四个条件复用 `S_r` 及 `live_edge_seed=602800+r`。C、E 都跨 `p` 复用各自试次的随机边数组，以 `U<p` 产生嵌套的有效边集合。E 的对照值取 E 当前试次的原图结果。
- D 在剩余全部节点上数连通分量，报告 GCC 节点数及其占原图比例，平均路径只在该 GCC 上计算。等大的 GCC 取最小节点 ID 较小者。路径用无权最短路，每批 128 个起点，排除对角线，以 `GCC_Size × (GCC_Size−1)` 为分母。固定条件的 `Trial_ID` 留空。
- C、E 汇报各条件的 Mean ± SD，并用 200 个配对试次的差值报告均值及双侧 95% t 区间。E 先逐试次计算 `100 × (同试次原图激活数 − 移除后激活数) / 同试次原图激活数`，再汇总。定向移除与随机移除比较使用同试次的下降率之差，以百分点报告。敏感性结果按 `p` 逐项解读。扩散结果对应模型设定下的模拟传播。

## Pilot 实测与参数依据

在 Apple M1、8 GB 内存上，用完整数据对每个 `p` 各跑 20 个试次，共 600 次 IC。结构测试包含原图、两种定向移除和 5 次随机移除。Pilot 所有 D/E 节点抽样与 C/E 传播种子均加 10,000，正式实验使用上节种子并独立生成结果。

| p | C PageRank 平均覆盖 | C Betweenness 平均覆盖 | E 原图平均覆盖 |
|---:|---:|---:|---:|
| 0.01 | 7.57% | 7.42% | 4.80% |
| 0.02 | 23.93% | 23.31% | 20.73% |
| **0.05** | **55.22%** | **55.19%** | **52.17%** |
| 0.10 | 75.72% | 75.78% | 74.82% |
| 0.20 | 89.41% | 89.44% | 87.95% |

- 保留 `p=0.05` 做主分析。此时 C 的覆盖约 55%，两组 Top-20 重合 10 个节点，pilot 中配对差均值仅 1.35 个节点。保留 200 次反映估计的不确定性。高 `p` 的 C 策略差异很小，E 的干预差异仍然可见，因此保留两个高 `p`。
- 全部 `p` 固定为 200 次。用 pilot 的配对标准差估算，E 在 `p=0.02` 比较 Betweenness 与随机移除时，95% 区间的预计半宽从 50 次的 4.21 个百分点降到 200 次的 2.06 个百分点。
- 批量核心实测每个 C 配对试次约 2–5 毫秒，每个 E 四条件试次约 4–9 毫秒。按各 `p` 平均耗时线性外推，C 约 3.3 秒、E 约 6.0 秒。D 的 53 次完整结构计算预计约 2.8 分钟。A 的精确 Betweenness 实测约 49 秒，B 的 Louvain 约 0.4 秒。整体 pilot 进程峰值约 280 MiB，含短路径批处理。外推计时覆盖计算核心，另计环境加载、文件读写、制图和报告制作。

## 复跑与记录

在项目目录运行 `python -m pilot.run_pilot`。附加 `--rebuild-centrality` 重算缓存的排名。原始 gzip 的 SHA-256 为 `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`。

正式输出延用 UTF-8 CSV。节点列表和逐轮激活数采用 JSON 数组。C、E 的记录键为 `(Trial_ID, Probability_p, Strategy)`，保留传播种子、激活总数、覆盖率与逐轮新增数。E 额外保存初始种子、移除集合与逐试次下降率。按概率批次复核行数、配对条件及试次标识。Pilot 已核对逐轮新增数之和、同一传播条件下移除后的激活数上界、各条件随 `p` 单调扩展，以及 D/E 重叠的随机移除集合。

[原始边表](data/raw/facebook_combined.txt.gz) · [Pilot 计时和统计](pilot/benchmark.json) · [中心性排名](pilot/centrality_scores.csv) · [C 逐次记录](pilot/seed_diffusion_trials.csv) · [D 逐次记录](pilot/structural_removal_results.csv) · [E 逐次记录](pilot/intervention_diffusion_trials.csv)
