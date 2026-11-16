# PREREG — enterprise-rag 预注册与评测规格

> 本文件是 enterprise-rag 的**预注册规格**（registered-report 风格）：声明本仓库**实际执行、可从落盘证据复算**的检索评测假设、评测方案、成功标准与明确边界。
> 所有数字来自仓库内文件（`results/`、`bench/`、`hybrid/`）与本地重算，**不是虚构实验**。

---

## 0. 一句话假设（先读这行）

> `results/hybrid_m1.json` 记录稀疏融合在 537 docs / 11994 chunks 上 recall@3 = 8、MRR 0.55。`results/dense_m2.json` 的 bge-small-zh 在同一 10 题上 recall@3 = 5/10、MRR@3 0.45，没有高于同文件稀疏臂（8/10、0.55）。`bench/results.json` 是另一次快照（546 docs / 12299 chunks），它的 `recall_at_5` 不是 gold recall，不能和 8/10 混写。语料缺失时 `HybridRetriever` 显式 `SystemExit`。n=10，无显著性声明。hardware: not recorded in the JSON files.

---

## 1. 主假设 H1（混合检索管线可运行可复算）

- **假设**：CSR 稀疏 TF-IDF + BM25 融合 + bigram 重排在真实语料上可运行、可复算，输出逐题明细。
- **可证伪方向**：若管线不可运行，或结果无法复算（逐题明细与汇总不一致），则 H1 不成立。
- **评测方案**：`hybrid/hybrid_rag.py`（M1）。`bench/bench_retrieval.py` 只是另一次延迟快照，它的 `recall_at_5` 不是 gold recall，不能当作 H1 的复算。
- **成功标准**：`results/hybrid_m1.json` 的 `main.rows` 能重算出 `recall_at_3` 和 `mrr`。`make check` 做这件事。它不要求 bench 与 hybrid_m1 数字相同。

## 2. 假设 H2（评测题集样本量约束）

- **假设**：评测题集仅 10 题（`demo/test_demo.py` 中 `summary["n"] == 10`），所有 recall/MRR 结论受此样本量限制。
- **可证伪方向**：若题集规模 ≥ 50 或跨语料，则 H2 不成立（当前边界如实声明）。
- **评测方案**：`EVAL_SET` 常量 + `bench/bench_retrieval.py` 的 `n_queries`。
- **成功标准**：`n_queries == 10`；M2 bootstrap 95% CI [0.2, 0.8]（宽区间如实报）。

## 3. 假设 H3（稠密未胜稀疏——真实负结果）

- **假设**：`results/dense_m2.json` 里 bge-small-zh recall@3 = 5/10、MRR@3 0.45，同文件稀疏臂是 8/10、MRR@3 0.55。该文件的 p50 是 dense 17.904 ms、sparse 5.459 ms。这是两份已提交字段，不是显著性检验，hardware: not recorded in this file。不要把 `hybrid_m1.json` 的 p50 7.56 ms 代进这个比值。
- **可证伪方向**：若稠密 MRR ≥ 稀疏 MRR 或更快，则 H3 不成立。
- **评测方案**：`hybrid/dense_rag.py --only zh`（需本地 HF 缓存 + 离线变量）。
- **成功标准**：`results/dense_m2.json` 数字与声明一致；负结果如实报告。

## 4. 假设 H4（fail-closed：语料缺失宁可失败）

- **假设**：语料缺失时**显式 SystemExit**，不产出看似合理的假数字（0 分）。
- **可证伪方向**：若语料缺失时静默出 0 或假结果，则 H4 不成立。
- **评测方案**：`hybrid/hybrid_rag.py` `HybridRetriever` 在 `load_corpus()` 为空时 `raise SystemExit`（当前在 `hybrid_rag.py` 约第 219 行；以源码为准，行号会漂）。
- **成功标准**：语料为空 → 显式错误退出，非静默 0 分。

---

## 5. 明确边界（不证明什么）

| 维度 | 不证明 | 原因 |
|---|---|---|
| 检索质量 | 5/5 baseline 证明链路跑通 | baseline 是 7 文档 10 chunk toy 规模 |
| ANN | 稠密是精确索引 | 11994 chunk 谈不上近似最近邻 |
| 跨题集迁移/拒答 | 迁移能力、拒答能力未验证 | 题集仅 10 题 |
| RAG 普适优劣 | "RAG 优于/劣于 X" | M2 负结果只在"10 题中文技术语料 + char-bigram + bge-small-zh"条件下成立 |
| 同义改写 | 没有同义改写题；这 10 题上 M2 也没有超过稀疏臂 | 不能把“处理不了同义”写成已测结论 |

---

## 6. 结论纪律

- 发布的 recall/MRR 从 `results/*.json` 的逐题行重算（`make check`）。`bench/results.json` 的 `recall_at_5` 不是这套 gold recall，不拿来复算 H1。
- baseline 冻结只读（recall@3 = 5/5、MRR = 1.000 可对照不可改）。
- M2 负结果只在该组条件下成立，不宣称普适结论。
- 本 PREREG 是规格声明，不新增实验，不改变已冻结 `hybrid/` 代码与 `results/` 基线。
