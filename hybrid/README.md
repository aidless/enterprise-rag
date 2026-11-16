# hybrid/ — 融合检索策略（M1 已实现）

> 本目录**曾经**是"契约文档位，不包含实现代码"。2026-10-11 的 M1 把契约做成了
> 能跑的代码，跑出来的数字（含两个无效改进）写在 [RESULTS_M1.md](RESULTS_M1.md)。

## 现在有什么

| 文件 | 内容 |
|---|---|
| `hybrid_rag.py` | 可运行的 hybrid 检索：多类型语料 → 句子感知分块 → CSR 稀疏 TF-IDF + BM25 → 融合 → bigram 重排。零网络、零 API key（依赖 numpy + scipy）。 |
| `dense_rag.py` | M2：换成真语义向量（本地 HF 缓存的 MiniLM / bge-small-zh）后的同题对比。必须 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`。 |
| `metamorphic_test.py` | M3：6 条 metamorphic relation，查"查询被等价改写后检索结果翻没翻"。 |
| `RESULTS_M1.md` | M1 的诚实结论：哪些设计点有效、哪些无效、出题踩了什么坑。 |
| `RESULTS_M3_METAMORPHIC.md` | M3 变异测试：归一化前后违反率、以及修正变换函数 bug 的经过。 |
| `../results/hybrid_m1.json` | 六项扫描的原始输出。 |
| `../results/dense_m2.json` | M2 dense vs sparse 对比 + bootstrap CI95。 |
| `../results/metamorphic_m3.json` | 每条关系 × 每个变异的逐条结果。 |

```bash
cd .. && python3 hybrid/hybrid_rag.py                 # M1，需要姊妹仓 + numpy/scipy
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python3 hybrid/dense_rag.py --only zh                # M2，另需本地 BAAI/bge-small-zh-v1.5
python3 hybrid/metamorphic_test.py                    # M3，需要同一姊妹仓
```

耗时不是 `results/*.json` 里的字段。缺姊妹仓时 `HybridRetriever` 会 `SystemExit`。`make check` 不跑上面三条。

## 设计意图（保留原文，便于对照"设计 vs 实测"）

- 基座语料 + 增量语料双路召回，按时间/来源加权融合，再进重排。
- 初排（向量检索 embedding + ANN）负责召回，重排（BM25 / 交叉编码器）负责精排。
- 参数（权重、TopK、候选数）见 `config/bline.yaml`，本目录只定义"融在哪个环节、输什么、收什么"。

## M1 相对冻结 baseline 的真实差异

| 维度 | baseline（冻结只读） | M1 |
|---|---|---|
| 语料 | 7 docs / 10 chunks，仅 `.md` | 537 docs / 11994 chunks，`.md/.py/.yaml/.json/.txt` |
| 索引 | dense 逐点积 | scipy CSR 稀疏。延迟只引用 JSON，不在这里另写一个倍数 |
| 过滤 | 无 | 跳过 `tokenizer.json`、`*.safetensors`、`>200KB` 文档 |
| recall@3 / MRR | 5/5 / 1.000（小库口径） | **8/10 / 0.55**（大库口径） |

**两边的数字不可直接比**：语料扩大约 1200 倍。`baseline/` 保持只读，`recall@3=5/5` 只作对照。

## 消融结论（短版，详见 RESULTS_M1.md / RESULTS_M3_METAMORPHIC.md）

- **和 JSON 一致的结果**：`results/hybrid_m1.json` 主结果 recall_at_3 = 8、MRR 0.55、p50 7.56 ms（hardware: not recorded）。`rerank_ablation.delta_recall` = 0。`sweep` 里 MRR 最高的是 w_cos=0.0 的 0.6333，但这是同一 10 题，不是留出集；主配置仍是 w_cos=0.6。`results/dense_m2.json` 里 bge-small-zh 是 5/10、MRR@3 0.45，同文件稀疏臂是 8/10、0.55，p50 分别是 17.904 ms 和 5.459 ms。`results/metamorphic_m3.json` 的 INVARIANT 是 6 → 0，DESIRABLE 归一化后仍是 8。
- **不能写成结论的**：n=10，bootstrap 区间重叠，无显著性声明。overlap 扫描的 MRR 是 0.5833、0.55、0.55、0.625（overlap 0/20/40/80），非单调，且与主结果同一题集。
- **文件里没有、因此这里不引用的**：一份英文 encoder 的分数，以及任何不在 `results/*.json` 里的加速倍数。

## 尚缺（不要对外说这是"生产级"）

- 重排信号需要语义级（cross-encoder / embedding），否则第三级永远是冗余的。
- 题集 10 题做不出统计结论；扩到 50+ 题才能下"有效/无效"。
- 没有拒答/负例场景。
- 中文停用词表（MR-6 残余 1 例，IDF 压不住"的/麻烦"这类虚词）。
- `golden/`、`latency/`、`harness/`、`reranker/` 仍是空契约目录。
- `dense_rag.py --only hy` 是**未完成占位**（score_dense 未实现，跑它只会复现 sparse 数字）。

## 状态

M1 已跑通（2026-10-11）。M2 真语义向量对比、M3 变异测试同日完成，但都不是生产级实现；
下一步见 RESULTS_M1.md 末尾。
