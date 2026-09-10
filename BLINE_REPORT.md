# B 线（enterprise-rag）迁移准备报告

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

## 3. 本仓纳入清单（骨架，零核心检索代码）

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
- **核心检索代码**（融合/重排/评测的生产实现）——本仓暂不写，留待后续里程碑。
- **远端仓 / 推送 / 发布**——需用户另行授权，本仓为纯本地骨架。

## 5. 状态

本地迁移准备骨架**就绪**，零核心代码、零密钥、零绝对路径残留；下一步（需授权）才是"建远端空仓并推送"。