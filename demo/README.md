# RAG 检索证据回放 Demo

[**Live demo**](https://aidless.github.io/enterprise-rag/) · 本地查询与结果回放见下。

**一句话**：RAG 检索跑通不等于检索质量；负结果也是结果。
这个 Demo 回放已提交的实验结果，并在本地跑冻结基线；11994-chunk 的私有语料不在仓内。

## 30 秒开始

```bash
cd enterprise-rag
python3 demo/server.py                  # http://127.0.0.1:8000/
```

本地模式提供：

- `GET /api/health`
- `GET /api/results` / `GET /results.json`
- `POST /api/query`：只在 7 docs / 10 chunks 的冻结基线上检索
- `POST /api/run`：重建结果回放
- `GET /config.json`：`{"mode": "live"}`

静态回放：

```bash
python3 demo/build_static.py            # 写 demo/public/results.json
python3 -m http.server -d demo/public   # 任意静态服务器
```

构建脚本会把回放值与三份结果 JSON 逐项对账；对不上以非零退出码结束。

## 测试

```bash
python3 -m unittest demo/test_demo.py -v
```

覆盖：结果值与源 JSON 一致、负结果显式、逐题 sparse/dense 对比、按 MR 拆解、
冻结基线查询与静态示例、已提交 `results.json` 与当前代码一致、UI 不硬编码指标、
无密钥/绝对路径、本地 HTTP API。

## 页面怎么读

1. 顶部五个数字：M1 稀疏 recall、M2 dense recall、归一化修复数、DESIRABLE 剩余违规、重排 Δrecall。
2. 四张层卡：冻结基线、M1 稀疏融合、M2 真语义向量、M3 变异测试；每张卡标注 scope、指标和来源。
3. 消融表：
   - bigram 重排 on/off 完全相同，delta_recall=0；
   - w_cos 扫描的最佳点是 BM25-only，不是照搬的 0.6；
   - overlap 扫描的最佳点不是默认的 40；
   - candidates 从 10 到 500 都没变，截断不是瓶颈。
4. 逐题对比：sparse 8/10、dense 5/10；3 条 sparse-only、0 条 dense-only、5 条 both、2 条 neither。
   dense 没有在任何一题上单独赢过 sparse。
5. 变异关系拆解：MR-2 修掉 4 条，MR-3 修掉 2 条；DESIRABLE 的 MR-4/5/6 仍各剩 1–3 条。
6. 本地查询：点示例按钮，或输入 `RAG 由哪几部分组成` 看冻结基线 top-3；它不碰私有语料。
7. 底部 findings/refutes：把“这组实验说明了什么”和“不证明什么”分开。

## 三分钟面试讲法

1. 先讲边界：11994-chunk 语料不在仓内，页面回放已提交结果；本地查询只跑 7-doc 冻结基线。
2. 讲主结果：M1 8/10 recall、MRR 0.55；M2 dense 5/10、MRR 0.45，没赢稀疏融合而且更慢。
3. 讲负结果：bigram 重排 on/off 完全相同；w_cos=0.6 不是最优；overlap=40 不是最优。
4. 讲逐题：dense 的 5 个命中全部落在 sparse 也命中的 extended 题上；3 条 sparse-only 都在 baseline 题；
   2 条 neither 是 chunking 和做饭干扰项。没有 dense-only。
5. 讲变异测试：归一化把 INVARIANT 6→0、DESIRABLE 11→8；MR-2/3 修掉 6 条，MR-4/5/6 仍剩 8 条。
6. 讲判断：这组数字的价值不在某个高分，而在“哪些改进真的动了指标、哪些没有”。

## 真实与回放

| 类别 | 说明 |
|---|---|
| 真实 | 数字来自 `results/hybrid_m1.json`、`results/dense_m2.json`、`results/metamorphic_m3.json`；本地查询跑 `baseline/rag_demo.py` |
| 回放 | 11994-chunk 私有语料不重跑；页面只回放已提交结果 |
| 不是 | 生产 RAG、统计显著的检索质量结论、或私有语料的可复现实验 |

## 文件

```text
demo/
├── payload.py            # 读取三份结果 JSON + 冻结基线查询
├── build_static.py       # 生成 public/results.json
├── server.py             # stdlib HTTP，静态页 + /api/query
├── public/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── config.json
│   └── results.json
├── test_demo.py
└── README.md
```

## 边界

- 题集只有 10 题，语料 537 docs / 11994 chunks；不是生产基准。
- 冻结基线 5/5 是 7 docs / 10 chunks 的 toy，只证明链路跑通。
- dense 用中文 BGE，但题集含 1 条英文 query；语言不匹配是未分离的协变量。
- 变异关系是手选的 6 条，不是穷尽集合。
- `results.json` 不参与 `worktree_dirty` 判断。
