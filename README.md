# enterprise-rag

[![CI](https://github.com/aidless/enterprise-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/enterprise-rag/actions/workflows/ci.yml)

**STATUS: WORK-IN-PROGRESS — not A yet.** The gaps are listed under [Remaining gaps](#remaining-gaps). Retrieval numbers in the block below are rendered from committed JSON by `check/recompute.py`. Do not edit that block by hand.

<!-- EVIDENCE:BEGIN -->
On the one 10-question set in `results/hybrid_m1.json` and `results/dense_m2.json`, sparse fusion recall@3 is 8/10 (MRR 0.55) and `BAAI/bge-small-zh-v1.5` recall@3 is 5/10 (MRR@3 0.45).
That comparison is this corpus snapshot only (537 documents / 11994 chunks) and this question set. It is not a generalization result and it is not an enterprise-readiness result.
With only those 10 questions, recall bootstrap 95% intervals are sparse 0.5–1.0 and dense 0.2–0.8 (seed 20261011, 5000 resamples, recomputed from the per-question hits). The intervals overlap. This repository does not claim that sparse beats dense.

## Published sparse result (`results/hybrid_m1.json`)

Strict top-3 recount from `main.rows`: recall 8/10, MRR 0.55, max hit rank 3. Stored fields: recall_at_3 8, mrr 0.55, recall_rate 0.8, corpus 537 / 11994.
`hybrid/hybrid_rag.py` `evaluate()` calls `retrieve(..., k=5)` while the field is named recall_at_3. In this file every recorded hit rank is <= 3, so the strict top-3 recount equals the stored field. The name and the call are not the same definition.
Stored latency on this run: p50 7.56 ms, p95 29.09 ms. hardware: not recorded in this file.
Same-set sweeps, not held-out tests: best `sweep` row is w_cos 0.0 with MRR 0.6333; the reported main config is w_cos 0.6. Best `overlap_study` row is overlap 80 with MRR 0.625. `rerank_ablation.delta_recall` is 0.

## Same questions, dense arm (`results/dense_m2.json`)

Model `BAAI/bge-small-zh-v1.5`, dim 512, build_s 18.088. Dense strict top-3 recount 5/10, MRR 0.45 (stored 5/10, MRR@3 0.45). Sparse arm in this file: 8/10, MRR 0.55 (stored 8/10, MRR@3 0.55).
Stored latency in this file, sparse arm p50 5.459 ms / p95 47.01 ms; dense arm p50 17.904 ms / p95 109.828 ms. hardware: not recorded in this file. A ratio of those two p50 fields is not stored, and this block does not add one. Do not substitute `hybrid_m1.json` p50 for the sparse p50 in this file; it is a different stored timing.
No English-encoder metrics are in this file. `hybrid/dense_rag.py` names `sentence-transformers/all-MiniLM-L6-v2`, and running that path requires the model already on disk. This block does not cite an English-encoder score.

| question | sparse rank | dense rank |
| --- | --- | --- |
| RAG 由哪几部分组成 | 3 | miss |
| 分块太大或太小各有什么影响 | miss | miss |
| 向量数据库怎么选型和调优 | 3 | miss |
| 如何评估问答系统的效果 | 2 | miss |
| 番茄炒蛋怎么做 | miss | miss |
| 翻转率 分层 判定标准 | 1 | 1 |
| McNemar 检验 样本量 门槛 | 1 | 1 |
| QLoRA 4bit 量化 LoRA rank | 1 | 1 |
| 成本 协商 非劣效 | 3 | 2 |
| 门禁 零耦合 反作弊 | 1 | 1 |

## Bootstrap recomputed from those rows

Recall, same algorithm as `hybrid/dense_rag.py` `bootstrap_ci` (seed 20261011, 5000 resamples): sparse 0.5–1.0 (committed 0.5–1.0); dense 0.2–0.8 (committed 0.2–0.8).
MRR bootstrap is not stored in the JSON. Recomputed here from per-question reciprocal rank: sparse 0.3167–0.8, dense 0.15–0.75.
Paired (sparse hit − dense hit) mean 0.3, bootstrap 95% interval 0.0–0.6. This is a description of these ten paired rows, not a significance test.

## Metamorphic (`results/metamorphic_m3.json`)

Recounted INVARIANT violations: 6 before, 0 after (comparison block 6 → 0). DESIRABLE violations: 11 before, 8 after (rate after 0.2667). DESIRABLE failures are still failures of those relations; the normalizer did not clear them.

## Latency snapshot that is not gold recall (`bench/results.json`)

Stored corpus 546 / 12299, p50 4.425 ms, p95 29.423 ms, build_s 3.94. hardware: not recorded in this file. The field recall_at_5 is 10. `bench/bench_retrieval.py` sets it with `ok = bool(blob.strip())`, which is true when retrieval returns any text. It is not gold-document recall and it is not comparable to the 8/10 above.

## In-repo baseline

`baseline_frozen` in `hybrid_m1.json`: recall@3 5/5, MRR 1.0, 7 documents / 10 chunks. `make check` re-runs `baseline/rag_demo.py` and requires the printed `recall@3 = 5/5` and `MRR = 1.000`. That re-run is the sparse retrieval this clone can execute.
<!-- EVIDENCE:END -->

## What `make check` runs

`make check` is the fresh-clone path. It uses the Python standard library only. It does not install packages, does not download a model, and does not read the sister corpus.

It recounts recall@3 and MRR from the per-question rows, recomputes the percentile bootstrap with the same seed and index rule as `hybrid/dense_rag.py`, checks this evidence block and the docs for drifted phrases, checks the empty contract directories, and re-runs `baseline/rag_demo.py` (the only sparse index whose documents are in this clone). It also runs `demo/test_demo.py`.

```sh
make check
```

`make eval` is separate. It needs `numpy` and `scipy` already installed, imports `hybrid/hybrid_rag.py`, and runs `eval/run_cases.py` plus the demo contract tests. It still does not download bge.

## What needs a model, and what this clone cannot re-index

`python3 hybrid/dense_rag.py --only zh` needs two things that `make check` and CI do not fetch:

- a local cache of `BAAI/bge-small-zh-v1.5` (run with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; the script exits if the cache is missing)
- the sister corpus directories named in `hybrid/hybrid_rag.py`: `paper_workflow_kb`, `paper_agent`, `paper_joint_mem_forget`

The optional English encoder named in that script is `sentence-transformers/all-MiniLM-L6-v2`. No committed results file contains an English-encoder run, so this repository does not quote one. `hybrid/hybrid_rag.py` and `hybrid/metamorphic_test.py` also need that sister corpus plus `numpy` and `scipy`. If the corpus directories are missing, `HybridRetriever` raises `SystemExit`.

## Remaining gaps

1. GitHub About is outside git. The live description on 2026-11-16 was still the sentence quoted below as observed and false. This PR cannot change it. The replacement text is in the next section. The topics `chromadb` and `design-spec` do not match the tree: a search of the repository finds no chromadb use.
2. `make check` recounts the published 537-document metrics from rows. It does not re-index that corpus, because the sister repositories are not in the clone.
3. Latency hardware is not a field in `results/hybrid_m1.json`, `results/dense_m2.json`, or `bench/results.json`. The evidence block can only say so.
4. The question set is still those 10 questions. The weight, overlap, candidate, and rerank sweeps in `hybrid_m1.json` used the same questions. No held-out set was added.
5. `golden/`, `latency/`, `harness/`, and `reranker/` are still empty contracts. They are marked, not implemented.
6. `bench/results.json` `recall_at_5` counts non-empty retrieval text. It stays in the file as a latency snapshot with that definition, not as a corrected recall.

## GitHub About

Paste this over the repository description (350-character limit). It is the same string `check/recompute.py` builds from the question-set size in `results/hybrid_m1.json`:

> Local research repo: sparse vs dense retrieval on one 10-question set, with committed results. Not production and not enterprise-ready. n=10, no significance claim. golden/latency/harness/reranker are empty contracts.

Observed (false): 混合检索企业 RAG（BM25+向量）的设计文档：含评测指标方案；spec-only，仓库当前不含任何实现代码。

Also remove the topics `chromadb` and `design-spec`. There is no chromadb client in this repository, and the tree is no longer a design-only snapshot.

## Paths

Result rows name sister-repo files under `paper_workflow_kb/`, `paper_agent/`, and `paper_joint_mem_forget/`. Those are corpus-relative identifiers from the run that wrote the JSON, not author home directories, and the sister repositories are not shipped here. `CODEOWNERS` names the GitHub login `@aidless`. `.gitignore` notes that a sync tool called WorkBuddy added ignore rules on 2026-10-21; that is a tool label, not an enterprise user. `demo/test_demo.py` rejects `/Users/` and `C:\` patterns in the demo sources.

## Layout

| Path | What it is |
| --- | --- |
| `baseline/` | Frozen 7-document demo. `make check` re-runs it. |
| `hybrid/` | M1–M3 implementation. Full re-run needs the sister corpus. |
| `results/` | Committed `hybrid_m1.json`, `dense_m2.json`, `metamorphic_m3.json`. |
| `bench/results.json` | Later latency snapshot. Its recall field is not gold recall. |
| `demo/` | Replay of the committed JSON plus the frozen baseline. |
| `golden/` `latency/` `harness/` `reranker/` | Empty contracts. See each README. |
| `FAILURE_MODES.md` | Limits of the 10-question comparison. |
| `BLINE_REPORT.md` | Historical stage-1 snapshot, not current status. |

[Live demo workflow](https://aidless.github.io/enterprise-rag/) publishes `demo/public`. `demo/test_demo.py` checks that artifact against the JSON. This PR does not change `demo/public`.

## License

MIT. See `LICENSE`.
