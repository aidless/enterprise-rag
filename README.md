# enterprise-rag

> 企业级 RAG 检索侧的**本地迁移仓**：从 `rag_min_demo`（单文件 toy demo）向可参数化、可评测、可复算的检索管线演进。
>
> 状态：**M1–M3 已实现并跑出真实数字（2026-10-11），但不是生产级**。检索链路、真语义向量对比、变异测试都有可运行代码与落盘结果；缺 50+ 题集、语义级重排、负例拒答场景。

[**Live demo**](https://aidless.github.io/enterprise-rag/) · [Demo 文档](demo/README.md)

Demo 还包含逐题 sparse/dense 对比、按 MR 拆解的变异关系表，以及不依赖后端的静态示例查询。

## 30 秒看清这个仓在做什么

| 模块 | 状态 | 一句话 |
|---|---|---|
| `baseline/` | 冻结只读 | `rag_min_demo` 的 7 文档 10 chunk 玩具库，recall@3 = 5/5 / MRR = 1.000，只作对照不改 |
| `hybrid/` | ✅ 可运行 | CSR 稀疏 TF-IDF + BM25 融合 + bigram 重排；11994 chunk / 537 docs；recall@3 allow-number，MRR 0.55，p50 3.25ms |
| `hybrid/dense_rag.py` | ✅ 可运行 | M2：本地 bge-small-zh 语义向量对同一题集，recall@3 = 5/10、**MRR@3 0.450**，没赢稀疏融合（稀疏 MRR 0.550），慢约 3 倍（p50 17.9ms vs 5.5ms） |
| `hybrid/metamorphic_test.py` | ✅ 可运行 | M3：6 条 metamorphic relation，查询侧归一化后 INVARIANT 命中归零 |
| `golden/` `latency/` `harness/` `reranker/` | ❌ 空契约 | 仍是 README 设计位，没有实现 |

## 诚实边界（先说清，避免误读）

**本仓证明了什么：**

- 一条**可运行、可复算**的稀疏+稠密混合检索管线：CSR 稀疏 TF-IDF + BM25 融合 + bigram 重排，在 537 文档 / 11994 chunk 语料上跑出 recall@3 = 8/10、MRR 0.550（`results/hybrid_m1.json`），并有逐题明细。
- 一个**真语义向量对照**（M2）：bge-small-zh 对同一题集 recall@3 = 5/10、MRR@3 0.450，**没赢**稀疏融合，且 p50 慢约 3 倍（17.9ms vs 5.5ms）——这是本仓的一个真实负结果。
- 一套**变异测试**（M3）：6 条 metamorphic relation 声明了 INVARIANT（必须成立）与 DESIRABLE（非强制）两类；查询侧加归一化器后 INVARIANT 违反从 6 → 0（`results/metamorphic_m3.json`）。
- 一个**可复现的 demo 工件**：`demo/test_demo.py` 15 个契约测试锁定提交结果值、负结果显式性、无手写指标、无密钥/绝对路径泄漏（全部通过，无需网络）。

**本仓不证明什么：**

- 冻结基线 `baseline/rag_demo.py` 的 recall@3 = 5/5、MRR = 1.000 是 **7 文档 10 chunk 的 toy 规模**：5/5 证明"链路跑通"，**不证明检索质量**。规模证据在 `paper_agent` 侧（54 万篇 FAISS 基座 + arXiv 增量），不在本仓。
- 字二元组 TF-IDF + BM25 处理不了同义改写；M2 换成真 embedding 后也**没有**在这个语料上赢。当前 `11994 chunk` 谈不上 ANN——这是稠密索引，不是近似最近邻。
- **评测题集只有 10 题**（`demo/test_demo.py` 里 `summary["n"] == 10`）。跨题集迁移能力、拒答能力均未验证。所有"有效/无效"结论都受这个样本量限制；10 题的 recall 置信区间宽（M2 bootstrap 95% CI [0.2, 0.8]）。
- 不宣称任何"RAG 优于/劣于 X"的普适结论。M2 的负结果只在"10 题中文技术语料 + char-bigram 分词 + bge-small-zh"这一组条件下成立。
- 运行依赖 **numpy + scipy**（dense 版另需本地 HF 模型缓存与 `sentence_transformers`）。语料默认从姊妹仓 `paper_workflow_kb/`、`paper_agent/`、`paper_joint_mem_forget/` 读取，缺目录会显式 `SystemExit` 而不是静默出 0 分——这是 fail-closed：语料缺失时宁可失败，不产出看似合理的假数字。

## 仓库结构

| 路径 | 性质 | 说明 |
| --- | --- | --- |
| `baseline/` | 冻结引用 | `rag_demo.py` + 7 文档，从 `rag_min_demo` 冻结复制，不改逻辑与语料（只读） |
| `hybrid/` | **可运行** | `hybrid_rag.py`（M1）/ `dense_rag.py`（M2）/ `metamorphic_test.py`（M3）+ 结果报告 |
| `results/` | 原始输出 | `hybrid_m1.json` `dense_m2.json` `metamorphic_m3.json` |
| `config/bline.yaml` | 配置位 | 基线参数（权重/TopK/分块上限）设计位，非实现代码 |
| `reranker/README.md` | 设计位 | 重排接口契约文档位（尚未实现） |
| `harness/README.md` | 设计位 | 评测驱动契约文档位（尚未实现） |
| `latency/README.md` | 设计位 | 延迟记录表位 |
| `golden/README.md` | 设计位 | golden 集契约（冻结期望文档） |
| `demo.sh` | 演示 | 调冻结基线做一键演示（只读） |
| `BLINE_REPORT.md` | 迁移报告 | 阶段一：冻结基线与参数位报告 |
| `LICENSE` | 许可 | MIT（由 `rag_min_demo/bline/LICENSE` 复制） |

## 复现

```sh
# 冻结基线（只读，仅标准库）
python3 baseline/rag_demo.py                       # 预期 recall@3 = 5/5, MRR = 1.000

# M1 hybrid 检索（约 3 分钟，需要姊妹仓在工作区/上级目录）
python3 hybrid/hybrid_rag.py

# M2 真语义向量对比（需本地 HF 缓存，必须离线变量）
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python3 hybrid/dense_rag.py --only zh

# M3 变异测试（纯 CPU，几秒）
python3 hybrid/metamorphic_test.py

# 检索延迟基准（focused，构建 + 10 题真实检索）
python3 bench/bench_retrieval.py    # → bench/results.json
```

### 基准结果（bench/results.json，2026-11-01 实测）

`bench/bench_retrieval.py` 构建 `HybridRetriever` 并对 10 题评测集做真实检索，输出：

| 指标 | 实测值 |
|---|---|
| 语料文档 / chunk | 546 / 12299 |
| 10 题 recall@5 | 10/10 |
| 检索延迟 p50 / p95 | 4.425 ms / 29.423 ms |
| 索引构建 | 3.94 s |

这是**检索延迟回归基线**（真实语料，非 toy）：语料随姊妹仓增长而增长（基线冻结时 537 docs / 11994 chunks，现 546 / 12299），延迟与 chunk 数相关。`load_config()` 返回 `(cfg_dict, tbd_used)` 元组——使用 `HybridRetriever` 时必须解包，否则报 `tuple indices must be integers`。

### 测试（无网络，锁定提交值）

```sh
# demo 契约测试：15 项，验证结果值、负结果显式性、无密钥/路径泄漏
make demo-test          # 或 python3 -m unittest demo/test_demo.py -v
```

注意 `demo/test_demo.py` 是**契约测试**——它断言 `demo/public/results.json`
与 `demo/payload.py` 当前重算一致，不重跑私有语料实验。若你改了
`demo/payload.py`，需先 `python3 demo/build_static.py` 重建工件，测试才会过。

## 明确非目标（Non-goals）

- 不对外宣称生产级；本仓是"迁移准备 + 消融实验"的载体，不是产品。
- ~~不建远端仓、不对外发布、不 `git push`~~ → **已变更（2026-10-21）**：本仓现已托管于 GitHub `aidless/enterprise-rag`（公开），由 WorkBuddy 接管同步。
- 不含 venv / 自指 symlink / 云凭证 / 向量库服务端与数据卷。
- 不改写冻结基线数字（recall@3 = 5/5、MRR = 1.000 只读，可对照不可改）。

## 许可

MIT（见 `LICENSE`）。