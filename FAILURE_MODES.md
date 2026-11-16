# Failure modes

These limits are properties of the committed files. They are not a new experiment.

## Tiny eval set

The published comparison uses the 10 questions in `results/hybrid_m1.json` `main.rows` and `results/dense_m2.json` `per_item`. A tiny eval set cannot support a significance claim. The README evidence block recomputes a percentile bootstrap (seed 20261011, 5000 resamples, the same index rule as `hybrid/dense_rag.py`). The recall intervals are wide and overlap, and the paired interval on (sparse hit − dense hit) includes 0. There is no significance claim.

## Question leakage

`results/hybrid_m1.json` records `sweep`, `cutoff_study`, `overlap_study`, and `rerank_ablation` on the same 10 questions as `main`. The highest sweep MRR is the `w_cos` 0.0 row. The reported main config remains `w_cos` 0.6. Choosing the sweep winner after seeing these questions would be question leakage into tuning. This repository does not promote that row to a held-out result. The overlap study is also non-monotonic on this same set, which is what a tiny eval set looks like.

## Tokenization and labels for Chinese

`hybrid/hybrid_rag.py` tokenizes with a char-bigram (`s[i:i+2]`). There is no Chinese word segmenter. Substring hints decide a hit. The cooking question is the sharp case: `EXPECT_HINTS` maps `cooking` to `python3` and `main.py`, not to a cooking document. A hit on that rule would not mean the recipe was retrieved. In the committed sparse rows that question is a miss. The baseline toy set in `baseline/rag_demo.py` uses document ids, which is a different label rule, so its 5/5 is not the same metric as the 10-question hint match.

## Metamorphic DESIRABLE failures

`results/metamorphic_m3.json` comparison block, recounted from the case rows by `make check`:

- INVARIANT violations before normalizer: 6
- INVARIANT violations after the query normalizer: 0
- DESIRABLE violations after normalizer: 8

DESIRABLE relations (word order, truncation, stopword-like additions) still fail after the normalizer. Reporting only the INVARIANT 6 → 0 change would hide those remaining failures. The relations are a hand-picked set of six, not an exhaustive suite.

## Empty contract directories

`golden/`, `latency/`, `harness/`, and `reranker/` each contain only a README. Each README starts with `EMPTY CONTRACT`. The bigram rerank that does exist is `Index.rerank` in `hybrid/hybrid_rag.py`, and its committed ablation did not change recall. It is not an implementation of the `reranker/` contract.

## Latency is three stored timings, and hardware is unlabeled

`hardware: not recorded` in `results/hybrid_m1.json` (p50 7.56 ms), in `results/dense_m2.json` (sparse p50 5.459 ms, dense p50 17.904 ms), and in `bench/results.json` (p50 4.425 ms on a 546 / 12299 snapshot). These are not one measurement. Do not average them or pick the smallest as "the" latency.

## `bench` recall is not gold recall

`bench/bench_retrieval.py` sets the committed `recall_at_5` with `ok = bool(blob.strip())`. A query counts as a hit when the retriever returns any text. The value 10 in `bench/results.json` is that definition. It does not mean the ten gold hints were found, and it does not overturn the two misses in `hybrid_m1.json`.

## The field `recall_at_3` is not the call

`hybrid/hybrid_rag.py` `evaluate()` calls `retrieve(..., k=5)` and stores the result under `recall_at_3`. In the committed file every true row has rank ≤ 3, so a strict top-3 recount matches the stored 8. The name and the call still disagree. `make check` fails if a future file records a hit at rank 4 or 5 while keeping the old summary, or if the recount and the summary diverge.

## The sister corpus is not in the clone

Re-running M1, M2, or M3 needs the sister corpus (`paper_workflow_kb`, `paper_agent`, `paper_joint_mem_forget`) beside this repository. `make check` does not pretend to do that. It recounts the committed rows and re-runs only `baseline/rag_demo.py`.

## GitHub About

The GitHub About description is not in git. The text observed on 2026-11-16 says the repository has no implementation. That sentence is false relative to this tree. The replacement text is in `README.md`. The topic `chromadb` has no matching code.

## Numbers that were in prose and not in JSON

Earlier prose quoted timings and a speedup that are not fields of `results/*.json` or `bench/results.json`. Those sentences were removed. The README evidence block is the list of timings that are actually stored, plus quantities recomputed from the per-question rows.
