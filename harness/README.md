# harness/ — 评测驱动契约（设计位）

本目录为**契约文档位**，不包含实现代码。评测驱动的唯一权威是"实测数字可重算"，本目录定义重算规范。

## 设计意图

- golden 集冻结（查询 → 期望文档/答案），任何检索改动只新增对照、不改冻结数字。
- 评测产物逐次落盘（含 SHA / 参数快照 / 时间戳），可独立重算。

## 位置（占位）

- `eval_contract.md`（规划）：评测入口、指标（recall@k / MRR / grounding）、复算命令。
- 无 `.py` 实现。

## 状态

TBD —— 冻结基线 `baseline/rag_demo.py` 自带 `EVAL_SET` 与 evaluate 函数（toy 规模）；生产评测 harness 待后续里程碑。