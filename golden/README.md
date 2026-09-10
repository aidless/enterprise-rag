# golden/ — golden 集契约（设计位）

本目录为**契约文档位**，不包含实现代码。

## 设计意图

- golden 集冻结：查询 → 期望文档（`doc_id`）/期望答案，落盘后不可变。
- 任何检索链路改动只能对照 golden 集新增评测结果，不得改写 golden 集本身。

## 位置（占位）

- 无文件，仅本 README。冻结基线自带的 5 题 golden 集在 `baseline/rag_demo.py` 的 `EVAL_SET`（只读引用）。

## 状态

TBD —— 生产级 golden 集（更多查询 + 期望文档/答案 + 出处）待后续里程碑构建。