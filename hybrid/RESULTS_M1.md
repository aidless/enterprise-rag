# M1 hybrid 检索：跑通了，但两个改进是无效的

**结论先说**：我把 `enterprise-rag` 的契约骨架做成了能跑的 hybrid 检索（537 docs → 11994 chunks），
但消融结果显示：**我原打算做的两个"改进"里，一个是真实提升，两个几乎无效**。
这些是脚本跑出来的数字（`results/hybrid_m1.json`），不是我预期的数字。

## 复现

```bash
cd enterprise-rag
python3 hybrid/hybrid_rag.py          # 约 3 分钟，纯 numpy+scipy，零网络
```

## 与冻结 baseline 的关系（口径必须讲清楚）

| | baseline（冻结，不可改） | M1 hybrid（本实现） |
|---|---|---|
| 语料 | 7 docs / 10 chunks | **537 docs / 11994 chunks** |
| 文件类型 | `.md` 只读 | `.md/.py/.yaml/.json/.txt`，过滤掉 `tokenizer.json` 等产物 |
| 索引 | baseline 的 dense 字二元组 | scipy CSR 稀疏 |
| 延迟 | 不在 baseline 结果里 | `hybrid_m1.json` p50 7.56 ms / p95 29.09 ms；hardware: not recorded。不要和 `dense_m2.json` 稀疏臂 p50 5.459 ms 当成同一次计时 |
| recall@3 | 5/5 | **8/10** |
| MRR | 1.000 | **0.55**（w_cos=0.6） |

**baseline 的 5/5 和 1.000 是在 10 个 chunk 的小库上取得的**；`hybrid_m1.json` 的语料是 11994 chunks，主结果是 8/10 / 0.55。这两个数字不能直接比。
`baseline/` 目录保持只读，本文件不修改它。

## 六项扫描结果（全部来自同一次运行）

| 实验 | 结果 | 判读 |
|---|---|---|
| w_cos/w_bm25 权重扫描（7 点） | w_cos=0.0 的 MRR 是 0.6333，recall_at_3 仍是 8；w_cos≥0.4 时 MRR 是 0.55 | 同一 10 题上的扫描，不是留出集。主结果仍报告 w_cos=0.6 |
| candidates 截断（10→500） | recall 全程 8/10，无变化 | **我原以为 candidates=10 会漏 gold，实测不成立** —— gold 在 fused 前 10 内 |
| overlap 消融（0/20/40/80） | MRR 0.5833、0.55、0.55、0.625 | 非单调。这是 10 题小集上的同一题扫描，不下“overlap 有效”的结论 |
| rerank ON/OFF | recall 8/10、MRR 0.55 **完全相同** | **我的第三级重排信号零贡献**。bigram 覆盖率与 fused 同源，没有引入新信息 |
| 延迟 | `main.latency_ms_p50` = 7.56，`latency_ms_p95` = 29.09 | 这是该 JSON 里的字段。hardware: not recorded。先前写在这里的另一组 p50/p95 不是这个字段，已删 |
| 题集 | baseline 5 题 + extended 5 题 = 10 题 | 见下方"出题踩坑" |

## 我做错/做对的事（如实记录）

**做对了的**
1. **扩展名写在代码里，因果没有单独的消融**。`INDEX_EXTS` 包含 `.md`、`.py`、`.yaml`、`.yml`、`.json`、`.txt`。`main.rows` 里 5 条 extended 都是 hit。JSON 里没有“只索引 markdown”的对照，所以这 5 个命中不能单独记成文件类型的功劳。
2. **稀疏索引是这份实现实际在跑的结构**。以前写在这里的 dense 点积耗时不在 `results/*.json` 里，已删除。能引用的延迟只有 JSON 里的 p50/p95，且 hardware: not recorded。
3. **产物过滤写在 `SKIP_NAME_RE` 里**。过滤前后的 chunk 计数不在提交的 JSON 里，所以这里不写“滤掉了多少”。

**做错了的**
1. **rerank 设计错了**：我用 bigram 覆盖率做第三级信号，但它与 cosine 的
   char-bigram 论据同源，信息量不独立 → 零贡献。真要重排需要语义级信号
   （cross-encoder 或 embedding 相似度），但那不是零依赖能做的。
2. **融合权重的方向感错了**：我把 `w_cos=0.6` 当默认（因为 baseline 是 0.6），
   扫描才发现纯 BM25 更好。**照搬 baseline 参数不等于最优**。
3. **两道题的当前标签**（以现在的 `EXPECT_HINTS` 和 `main.rows` 为准）：
   - `"番茄炒蛋怎么做"` 的 hint 是 `python3` 和 `main.py`，不是菜谱文档名。该行 `ok` 是 false。
   - `"分块太大或太小各有什么影响"` 的 hint 是 `chunk`。该行 `ok` 是 false。

## 这个 M1 该怎么定性

README 里我原来写的是"生产级实现待后续里程碑"。M1 之后的状态更准确的说法是：

> **一条能跑的 hybrid 检索链路 + 一组落在 JSON 里的消融数字**：文件类型扩展让工程事实进了索引；rerank 的 `delta_recall` 是 0；默认 `w_cos=0.6` 的 MRR 低于同一题集上 w_cos=0.0 的 0.6333，但那次扫描不是留出集。它**不是**生产级检索器。`golden/`、`latency/`、`harness/`、`reranker/` 仍是空契约。一份以前写在这里的加速倍数不在 `results/*.json` 里，已从本文删除。

## M2：换真语义向量之后，稀疏融合仍然没输（`results/dense_m2.json`）

M1 的"下一步"第 1 条是"换重排信号"，理由是第三级 rerank 用 bigram 覆盖率
与 cosine 同源、零贡献。M2 正面做这件事：把整个检索链路的主排序换成
**真语义向量**（`sentence-transformers`，本地模型，不联网、不需要 key）。

| 配置（`results/dense_m2.json`，同一 10 题） | recall@3 | MRR@3 | p50 | CI95 |
|---|---|---|---|---|
| 稀疏臂 `main_sparse_m1cfg` | **8/10** | **0.55** | 5.459 ms | [0.5, 1.0] |
| dense `BAAI/bge-small-zh-v1.5` | 5/10 | 0.45 | 17.904 ms | [0.2, 0.8] |

hardware: not recorded in this file. `hybrid_m1.json` 自己的 p50 是 7.56 ms，不要和 5.459 ms 合成一个数。

**但这里的正确结论不是"dense 不如 sparse"。** 必须同时讲三件事：

1. **英文 encoder 的分数不在提交文件里**。`dense_rag.py` 可以加载
   `sentence-transformers/all-MiniLM-L6-v2`，但 `results/dense_m2.json` 没有那次运行，
   所以这里不引用它的 recall。文件里有的语言事实是 `query_lang`：zh 9、en 1。
   评测之前先看 query 语言，这个提醒还在；没有落盘的分数不能当成结果。
2. **分型看完全反过来**：dense 在 `extended` 5 题上是 **5/5**（和稀疏并列），
   在 `baseline` 5 题上是 **0/5**。也就是说 sparse 赢的 3 题全在 baseline 层。
   两类题 query 风格不同，10 题的合计数字会把这个差异抹掉。
3. **代价里能引用的字段**：`dense_zh.build_s` = 18.088。稀疏索引的构建时间不在
   `hybrid_m1.json` 里。查询 p50 是上面表里的 17.904 ms 和 5.459 ms。
   不要把缺席的稀疏构建时间补成一个倍数。

**诚实的边界**：n=10、CI95 重叠（[0.2,0.8] vs [0.5,1.0]），这**不能**
推广为"embedding 在中文小语料上没用"。能说的只有：在这条语料、这个 10 题集合上，
真语义向量没有超过我在 M1 用 char-bigram 拼出来的稀疏融合。

复现（需要本地 HF 缓存里有这两个模型，全程离线）：

```bash
cd enterprise-rag
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 hybrid/dense_rag.py --only zh,sp
```

> 上表只覆盖已提交的 `zh` 对照。把英文 encoder 加进命令不会在本仓库里找到一份
> 已提交的英文分数；没有那份 JSON，就不写那个分数。

## 下一步（真的值得做的）

1. **换重排信号**：用 `sentence-transformers` 或本地小模型做 cross-encoder，
   否则第三级信号永远是冗余的。
2. **扩题集**：10 题做不出统计结论（overlap 非单调就是样本量症状）。
   要下任何"有效/无效"的结论，至少需要 50 题以上 + 分层报告。
3. **补负例**：现在的 10 题全是"语料里有答案"的正例，
   没有"语料里没有"的拒答场景（`番茄炒蛋` 本该是这个角色，但被我写成出题失败了）。

## 还没做的（别让上面的数字看起来比真实进度好）

- M2 只是换了主排序信号，**golden/latency/harness/reranker 四个目录
  仍然是只有 README 的契约位**，没有评测集规模、没有分层报告、没有负例拒答。
- `--only hy`（稀疏+中文 dense 的第四种融合配置）在 `dense_rag.py` 里是
  **未完成的占位**：`score_dense` 还没实现，跑它只会复现 `sp` 的数字。
- 题集仍是 10 题。上面所有"有效/无效"的判读都受此限制，不要在面试里
  把它当成统计结论讲——要讲的是过程：我把默认权重、rerank 信号、
  encoder 语言三个假设都逐个证伪或修正过。
