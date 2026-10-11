# M3-B 变异测试：MR-1/2/3 的违反全部由查询侧归一化修掉，且我先把一个错误的"缺陷"修掉了

**结论先说**：对 hybrid 检索（11994 chunks、10 题）跑 6 条 metamorphic relation，
得到 **30 个 INVARIANT 检查点 / 30 个 DESIRABLE 检查点**：

| 类别 | 归一化前违反 | 归一化后违反 | 差 |
|---|---|---|---|
| INVARIANT（MR-1 确定性 / MR-2 空白 / MR-3 大小写全角） | **6/30 (20%)** | **0/30 (0%)** | 全部修掉 |
| DESIRABLE（MR-4 词序 / MR-5 截断 / MR-6 停用词） | 11/30 (37%) | 8/30 (27%) | 修掉 3 例 |

复现（纯 stdlib + numpy/scipy，零网络）：

```bash
cd enterprise-rag
python3 hybrid/metamorphic_test.py          # 约 5s（含 4s 索引构建）
python3 hybrid/metamorphic_test.py --no-fix # 只看"归一化前"
```

结果：`results/metamorphic_m3.json`（每个检查点都带 `query / mr / mutated_query /
top3_base / top3_mut / violation / severity`，可逐条复现）。

## 我一上来发现的是我自己的 bug，不是检索器的 bug

第一版我把"转全角"写成 `chr(ord(c) - 0x20 + 0xFEE0)`，看着像那么回事。
实跑 MR-3 的明细里出现：

```
'McNemar 检验 样本量 门槛' -> '－Ｃ．ＥＭＡＲ 检验 样本量 门槛'
'QLoRA 4bit 量化 LoRA rank' -> '１，Ｏ２！ ﻴＢＩＴ 量化 ，Ｏ２！ ＲＡＮＫ'
```

`McNemar` 变成了 `Ｃ．ＥＭＡＲ`——**句点出现在了英文中间**，`4bit` 变成了 `Ｏ２！ ﻴＢＩＴ`（出现了阿拉伯字母区字符）。
原因是 `0xFFEE` 是全角编码里的空洞区间（半角片假名），`ord(c) - 0x20 + 0xFEE0` 对 `,` `.` 这类符号会落进
半角片假名区；正确公式是 `chr(ord(c) - 0x21 + 0xFF01)`（ASCII 可见 0x21–0x7E → 全角 U+FF01–U+FF5E）。

**这个坑值得单独记**：如果没修就出报告，我会得到"MR-3 违反 2 例、归一化也修不掉"的结论，
而真实原因是**我的变换函数产出了语料里不存在的字符**——那测的是变换函数，不是检索器。
变换函数的正确性本身需要被检验，这是变异测试比宣称"加了归一化"更可靠的地方。

修对之后，INVARIANT 违反从 6→0：

- MR-2（空白）4 例：`'  RAG   由哪几部分组成  \n'` 的 top-1 从
  `paper_workflow_kb/ROUND_R31.md` 翻到 `paper_joint_mem_forget/scripts/gate_citations.py`。
  原因很直白：**char-bigram 切分对空白敏感**——`"  RAG"` 会切出 `(' ',' ')` 这种垃圾 bigram，
  把真正有信息的 `RA`/`AG` 挤占权重，而所有 chunk 都带代码缩进所以都受影响。
- MR-3（大小写/全角）2 例：修对映射 + NFKC 后消失。

归一化只加在**查询侧**（索引不动），实现是
`unicodedata.normalize("NFKC", q)` + ASCII 大小写折叠 + 空白折叠。

## DESIRABLE 的残余违反不必修，但要能解释

剩下 8 例不修，因为它们分别指向 char-bigram 的**两个固有属性**，不是 bug：

1. **MR-4 词序（4 例）**：`'向量数据库怎么选型和调优'` 打乱成
   `'调优和选型怎么数据库向量'` 后 top-3 仍是同一个 doc
   （`paper_agent/reports/RETRIEVAL_UPGRADE.md` 三个 chunk）——top1 稳，但
   `'QLoRA 4bit 量化 LoRA rank'` 打乱后 top-1 从 `evidence/rater2_r12.json`
   变成 `scripts/apply_R24.py`。char-bigram 本就不保序，bag-of-words 假设成立时它才稳。
2. **MR-5 截断（4 例）**：`'成本 协商 非劣效'` 去掉末尾词后 top-1 从
   `paper_joint_mem_forget/ROUND_R1.md` 翻到 `paper_workflow_kb/ROUND_R22.md`——
   短 query 的信息量本来就少，这是查询长度敏感性，不是缺陷。
3. **MR-6 停用词（3 例中的 1 例）**：`'番茄炒蛋怎么做'` 前后加 `'麻烦'` / `'的'` 后
   top-3 完全换了一批 doc。**这一例最值得警惕**：加两个高频词就整体翻盘，
   说明 char-bigram 的 IDF 压不住中文高频虚词。真要修，该加中文停用词表（我没做）。

## 由此得出的下一步（和 M1/M2 一致，仍未做完）

- 归一化**已经从收益变成必须**：20% → 0% 是"能不能用"的差别，不是"好不好"的差别。
  下一步应把 `normalize_query` 接进 `HybridRetriever.retrieve`（或配置开关），
  现在它还只在 `metamorphic_test.py` 里。
- 需要中文停用词表，否则 MR-6 那一类违反会以"用户的自然口语"形式在产品里出现。
- 10 题仍然是 10 题。上面所有比率的分母都只有 30，只能说明"存在这类违反"，
  不能说明"违反率是 20%"。别在面试里把 20% 当统计数字讲。
