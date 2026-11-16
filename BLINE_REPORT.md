# B 线（enterprise-rag）迁移准备报告

> HISTORICAL SNAPSHOT, stage 1, written before M1. This file is not the current status. Current evidence is `README.md`. Sentences below describe that earlier skeleton.

> 冻结声明：`baseline/rag_demo.py` 与 `baseline/docs/`（即 `baseline/` 下 7 个文档）为 `rag_min_demo` 的**只读冻结复制**，本仓不改其逻辑与语料。
> 基线数字冻结：recall@3 = 5/5，MRR = 1.000（只可对照，不可改写）。

## 1. 脱敏结论（沿袭 rag_min_demo，2026-09-10 已实查）

| 检查项 | 结果 |
| --- | --- |
| 真实密钥（sk- / AKIA / Bearer 长 token / 明文 password=） | 通过：0 命中 |
| `/data1`、Administrator、`C:\Users\Administrator`、`F:\` 绝对路径 | 通过：0 命中 |
| Token 变量名残留（TOKEN / API_KEY / SECRET / PASSWORD） | 通过：0 命中 |
| 自指 symlink | 通过：无 |
| venv / .venv | 通过：无 |

## 2. LICENSE

- `LICENSE`：MIT（由 `rag_min_demo/bline/LICENSE` 复制，Copyright 2026 rag_min_demo contributors）。

## 3. 阶段一写入时的清单（当时还没有 hybrid 实现）

| 类别 | 路径 | 状态 |
| --- | --- | --- |
| 许可 | `LICENSE` | 已落盘（MIT） |
| 基线复用（只读引用） | `baseline/rag_demo.py` + `baseline/` 7 文档 | 已复制（冻结） |
| 配置 | `config/bline.yaml` | 已落盘（设计位，含 TBD） |
| 混合检索 | `hybrid/README.md` | 已落盘（契约文档位） |
| 重排 | `reranker/README.md` | 已落盘（契约文档位） |
| 评测 harness | `harness/README.md` | 已落盘（契约文档位） |
| 延迟 | `latency/README.md` | 已落盘（记录表位） |
| golden 集 | `golden/README.md` | 已落盘（契约文档位） |
| 评测结果 | `results/README.md` | 已落盘（输出契约） |
| 演示脚本 | `demo.sh` | 已落盘（只读调基线） |
| 本报告 | `BLINE_REPORT.md` | 即本文件 |

## 4. 排除项 / 尚未做

- venv、`.venv`、依赖安装产物；自指 symlink；云凭证（`*.pem`、`*credentials*`）；向量库服务端与数据卷。
- 撰写本报告时，融合/重排/评测实现尚未写入。随后的 M1–M3 代码现在在 `hybrid/`，数字在 `results/`。本段不把当时的空骨架说成当前事实。
- 撰写本报告时，远端仓尚未作为本文件的交付物。仓库后来托管于 GitHub `aidless/enterprise-rag`。

## 5. 状态

阶段一快照当时是本地骨架。当前状态以 `README.md` 为准，不以本节为准。