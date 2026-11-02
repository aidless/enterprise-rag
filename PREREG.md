# PREREG — enterprise-rag 预注册与评测规格

> 本文件是 enterprise-rag 的**预注册规格**（registered-report 风格）：声明本仓库**实际执行、可从落盘证据复算**的检索评测假设、评测方案、成功标准与明确边界。
> 所有数字来自仓库内文件（`results/`、`bench/`、`hybrid/`）与本地重算，**不是虚构实验**。

---

## 0. 一句话假设（先读这行）

> enterprise-rag 是一条**可运行、可复算**的稀疏+稠密混合检索管线（CSR 稀疏 TF-IDF + BM25 融合 + bigram 重排），在真实姊妹仓语料（546 docs / 12299 chunks，2026-11-01 实测）上跑出 recall@3 = 8/10、MRR 0.550、p50 3-4ms；M2 真语义向量（bge-small-zh）在同一题集上**没有赢**稀疏融合（负结果）；语料缺失时**显式 SystemExit**（fail-closed）。

---

## 1. 主假设 H1（混合检索管线可运行可复算）

- **假设**：CSR 稀疏 TF-IDF + BM25 融合 + bigram 重排在真实语料上可运行、可复算，输出逐题明细。
- **可证伪方向**：若管线不可运行，或结果无法复算（逐题明细与汇总不一致），则 H1 不成立。
- **评测方案**：`hybrid/hybrid_rag.py`（M1）+ `bench/bench_retrieval.py`（focused 延迟基准）。
- **成功标准**：`results/hybrid_m1.json` 与 bench 重算一致；逐题明细齐全。

## 2. 假设 H2（评测题集样本量约束）

- **假设**：评测题集仅 10 题（`demo/test_demo.py` 中 `summary["n"] == 10`），所有 recall/MRR 结论受此样本量限制。
- **可证伪方向**：若题集规模 ≥ 50 或跨语料，则 H2 不成立（当前边界如实声明）。
- **评测方案**：`EVAL_SET` 常量 + `bench/bench_retrieval.py` 的 `n_queries`。
- **成功标准**：`n_queries == 10`；M2 bootstrap 95% CI [0.2, 0.8]（宽区间如实报）。

## 3. 假设 H3（稠密未胜稀疏——真实负结果）

- **假设**：bge-small-zh 真语义向量（M2）在同一题集上 recall@3 = 5/10、MRR@3 0.450，**没有赢**稀疏融合（MRR 0.550），且 p50 慢约 3 倍（17.9ms vs 5.5ms）。
- **可证伪方向**：若稠密 MRR ≥ 稀疏 MRR 或更快，则 H3 不成立。
- **评测方案**：`hybrid/dense_rag.py --only zh`（需本地 HF 缓存 + 离线变量）。
- **成功标准**：`results/dense_m2.json` 数字与声明一致；负结果如实报告。

## 4. 假设 H4（fail-closed：语料缺失宁可失败）

- **假设**：语料缺失时**显式 SystemExit**，不产出看似合理的假数字（0 分）。
- **可证伪方向**：若语料缺失时静默出 0 或假结果，则 H4 不成立。
- **评测方案**：`hybrid/hybrid_rag.py` `load_corpus()` 空 → `raise SystemExit`（hybrid_rag.py:222-225）。
- **成功标准**：语料为空 → 显式错误退出，非静默 0 分。

---

## 5. 明确边界（不证明什么）

| 维度 | 不证明 | 原因 |
|---|---|---|
| 检索质量 | 5/5 baseline 证明链路跑通 | baseline 是 7 文档 10 chunk toy 规模 |
| ANN | 稠密是精确索引 | 11994 chunk 谈不上近似最近邻 |
| 跨题集迁移/拒答 | 迁移能力、拒答能力未验证 | 题集仅 10 题 |
| RAG 普适优劣 | "RAG 优于/劣于 X" | M2 负结果只在"10 题中文技术语料 + char-bigram + bge-small-zh"条件下成立 |
| 同义改写 | 字二元组 TF-IDF + BM25 处理不了 | M2 换 embedding 后也没赢 |

---

## 6. 结论纪律

- 所有数字从本仓重算（`bench/bench_retrieval.py` + `results/*.json`）。
- baseline 冻结只读（recall@3 = 5/5、MRR = 1.000 可对照不可改）。
- M2 负结果只在该组条件下成立，不宣称普适结论。
- 本 PREREG 是规格声明，不新增实验，不改变已冻结 `hybrid/` 代码与 `results/` 基线。
