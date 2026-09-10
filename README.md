# enterprise-rag

> 企业级 RAG 检索侧的**本地迁移准备仓**：从 `rag_min_demo`（单文件 toy demo）向可参数化、可评测、可复算的检索管线演进。
>
> 状态：**骨架仓（pre-implementation）**。本仓当前**零核心检索代码**——只收录许可、冻结基线只读引用、设计位文档与配置位；真正的融合检索/重排/评测实现是后续里程碑，不在此处。

## 诚实边界（先说清，避免误读）

- 冻结基线 `baseline/rag_demo.py` 实测 recall@3 = 5/5、MRR = 1.000，但这是 **7 文档 10 chunk 的 toy 规模**：5/5 证明"链路跑通"，**不证明检索质量**。规模证据在 `paper_agent` 侧（54 万篇 FAISS 基座 + arXiv 增量），不在本仓。
- 字二元组 TF-IDF + BM25 处理不了同义改写；生产切 embedding + ANN。当前 `10 chunk` 谈不上 ANN。
- 本仓暂**未写任何生产检索代码**，`hybrid/`、`reranker/`、`harness/` 目前只有接口/契约文档位。

## 仓库结构（骨架地图）

| 路径 | 性质 | 说明 |
| --- | --- | --- |
| `baseline/` | 冻结引用 | `rag_demo.py` + 7 文档，从 `rag_min_demo` 冻结复制，不改逻辑与语料（只读） |
| `config/bline.yaml` | 配置位 | 基线参数（权重/TopK/分块上限）设计位，非实现代码 |
| `hybrid/README.md` | 设计位 | 融合检索策略文档位（初排 + 重排融合） |
| `reranker/README.md` | 设计位 | 重排接口契约文档位 |
| `harness/README.md` | 设计位 | 评测驱动契约文档位 |
| `latency/README.md` | 设计位 | 延迟记录表位 |
| `golden/README.md` | 设计位 | golden 集契约（冻结期望文档） |
| `results/README.md` | 设计位 | 评测输出契约 |
| `demo.sh` | 演示 | 调冻结基线做一键演示（只读） |
| `BLINE_REPORT.md` | 设计报告 | 迁移准备完整报告 |
| `LICENSE` | 许可 | MIT（由 `rag_min_demo/bline/LICENSE` 复制） |

## 明确非目标（Non-goals）

- 不在本仓写核心检索代码（融合/重排/评测实现留待后续里程碑）。
- 不建远端仓、不对外发布、不 `git push`（需另行授权）。
- 不含 venv / 自指 symlink / 云凭证 / 向量库服务端与数据卷。
- 不改写冻结基线数字（recall@3 = 5/5、MRR = 1.000 只读，可对照不可改）。

## 复现冻结基线（只读）

```sh
python3 baseline/rag_demo.py          # 全链路 + 评测，预期 recall@3 = 5/5, MRR = 1.000
python3 baseline/rag_demo.py --query "分块太大有什么坏处"
```

依赖：Python 3.8+，仅标准库。

## 许可

MIT（见 `LICENSE`）。