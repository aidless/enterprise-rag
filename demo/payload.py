"""Build the enterprise-rag evidence payload.

The 11994-chunk corpus is not in this repository. This demo replays the
committed result JSONs and, in local mode, runs only the frozen 7-doc/10-chunk
baseline. It never claims to rerun the private-corpus experiment.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

_baseline_cache = None


def _read(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _baseline():
    global _baseline_cache
    if _baseline_cache is None:
        baseline_dir = ROOT / "baseline"
        if str(baseline_dir) not in sys.path:
            sys.path.insert(0, str(baseline_dir))
        import rag_demo  # noqa: WPS433

        chunks, index = rag_demo.run_pipeline(verbose=False)
        _baseline_cache = (rag_demo, chunks, index)
    return _baseline_cache


def query_baseline(query: str) -> list[dict]:
    text = (query or "").strip()
    if not text:
        return []
    rag_demo, chunks, index = _baseline()
    results = rag_demo.retrieve(text, chunks, index, top_k=3)
    return [
        {
            "score": round(float(score), 6),
            "chunk_id": chunk["chunk_id"],
            "doc_id": chunk["doc_id"],
            "title": chunk["title"],
            "text": chunk["text"][:300],
            "chars": chunk["chars"],
        }
        for score, chunk in results
    ]


def _query_table(hybrid: dict, dense: dict) -> dict:
    sparse_rows = hybrid["main"]["rows"]
    dense_by_query = {
        item["q"]: item for item in dense["main_dense_zh"]["per_item"]
    }
    rows = []
    counts = {"both": 0, "sparse_only": 0, "dense_only": 0, "neither": 0}
    for sparse in sparse_rows:
        dense_item = dense_by_query.get(sparse["q"], {})
        sparse_hit = bool(sparse.get("ok"))
        dense_hit = bool(dense_item.get("hit"))
        if sparse_hit and dense_hit:
            delta = "both"
        elif sparse_hit:
            delta = "sparse_only"
        elif dense_hit:
            delta = "dense_only"
        else:
            delta = "neither"
        counts[delta] += 1
        rows.append({
            "q": sparse["q"],
            "level": sparse.get("level", ""),
            "lang": dense_item.get("lang", ""),
            "sparse_hit": sparse_hit,
            "sparse_rank": sparse.get("rank"),
            "dense_hit": dense_hit,
            "dense_rank": dense_item.get("rank"),
            "delta": delta,
            "source": (
                "results/hybrid_m1.json#/main/rows + "
                "results/dense_m2.json#/main_dense_zh/per_item"
            ),
        })
    return {
        "rows": rows,
        "summary": {
            "n": len(rows),
            "sparse_hits": sum(1 for row in rows if row["sparse_hit"]),
            "dense_hits": sum(1 for row in rows if row["dense_hit"]),
            **counts,
        },
        "note": "逐题对比；同一题集，sparse 8/10、dense 5/10。",
    }


def _metamorphic_table(metamorphic: dict) -> dict:
    runs = {run["tag"]: run for run in metamorphic["runs"]}
    before = {
        (case["query"], case["mr"], case.get("mutation", "")): case
        for case in runs["before_normalizer"]["cases"]
    }
    after = {
        (case["query"], case["mr"], case.get("mutation", "")): case
        for case in runs["after_normalizer"]["cases"]
    }
    by_mr = {}
    for key in sorted(set(before) | set(after)):
        b = before.get(key, {})
        a = after.get(key, {})
        mr = key[1]
        row = by_mr.setdefault(mr, {
            "mr": mr,
            "class": b.get("class") or a.get("class") or "",
            "total": 0,
            "before_violations": 0,
            "after_violations": 0,
            "fixed": 0,
            "examples": [],
        })
        row["total"] += 1
        bv = bool(b.get("violation"))
        av = bool(a.get("violation"))
        row["before_violations"] += int(bv)
        row["after_violations"] += int(av)
        row["fixed"] += int(bv and not av)
        if (bv or av) and len(row["examples"]) < 2:
            row["examples"].append({
                "query": key[0],
                "mutation": key[2],
                "before": bv,
                "after": av,
            })
    rows = sorted(by_mr.values(), key=lambda row: row["mr"])
    return {
        "rows": rows,
        "summary": {
            "relations": len(rows),
            "before": sum(row["before_violations"] for row in rows),
            "after": sum(row["after_violations"] for row in rows),
            "fixed": sum(row["fixed"] for row in rows),
        },
        "note": "按 MR 拆解 before/after；归一化只修掉部分关系。",
    }


def _baseline_examples() -> list[dict]:
    queries = [
        "RAG 由哪几部分组成",
        "分块太大或太小各有什么影响",
        "向量数据库怎么选型和调优",
    ]
    return [
        {
            "query": query,
            "results": query_baseline(query),
            "scope": "7 docs / 10 chunks 冻结基线",
        }
        for query in queries
    ]


def _git_snapshot() -> tuple[str, bool, list[str]]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        raw = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
        ignored = ("demo/public/results.json",)
        dirty_paths = [
            line[3:] for line in raw
            if len(line) > 3 and not line[3:].startswith(ignored)
        ]
        return commit, bool(dirty_paths), dirty_paths[:12]
    except Exception:
        return "unknown", False, []


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def build_payload(generated_at: str | None = None) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    hybrid = _read("hybrid_m1.json")
    dense = _read("dense_m2.json")
    metamorphic = _read("metamorphic_m3.json")

    baseline = hybrid["baseline_frozen"]
    hybrid_main = hybrid["main"]
    dense_main = dense["main_dense_zh"]
    sparse_same_run = dense["main_sparse_m1cfg"]
    comparison = metamorphic["comparison"]
    rerank = hybrid["rerank_ablation"]
    sweep = hybrid["sweep"]
    overlap = hybrid["overlap_study"]
    cutoff = hybrid["cutoff_study"]
    best_sweep = max(sweep, key=lambda row: (row["mrr"], row["recall_at_3"]))
    chosen_sweep = next(row for row in sweep if abs(row["w_cos"] - 0.6) < 1e-9)
    best_overlap = max(overlap, key=lambda row: (row["mrr"], row["recall_at_3"]))
    chosen_overlap = next(row for row in overlap if row["overlap"] == 40)

    mrs = sorted({
        case["mr"]
        for run in metamorphic["runs"]
        for case in run["cases"]
    })
    query_table = _query_table(hybrid, dense)
    metamorphic_table = _metamorphic_table(metamorphic)
    baseline_examples = _baseline_examples()

    layers = [
        {
            "id": "baseline",
            "title": "冻结基线",
            "scope": f"{baseline['corpus_docs']} docs / {baseline['corpus_chunks']} chunks",
            "tone": "neutral",
            "metrics": [
                {"label": "recall@3", "value": baseline["recall_at_3"],
                 "source": "results/hybrid_m1.json#/baseline_frozen/recall_at_3"},
                {"label": "MRR", "value": _fmt(baseline["mrr"]),
                 "source": "results/hybrid_m1.json#/baseline_frozen/mrr"},
                {"label": "docs", "value": baseline["corpus_docs"],
                 "source": "results/hybrid_m1.json#/baseline_frozen/corpus_docs"},
                {"label": "chunks", "value": baseline["corpus_chunks"],
                 "source": "results/hybrid_m1.json#/baseline_frozen/corpus_chunks"},
            ],
            "verdict": "链路跑通；这是 7 文档 toy，不是检索质量。",
        },
        {
            "id": "hybrid",
            "title": "M1 稀疏融合",
            "scope": f"{hybrid_main['corpus_docs']} docs / {hybrid_main['corpus_chunks']} chunks",
            "tone": "ok",
            "metrics": [
                {"label": "recall@3", "value": f"{hybrid_main['recall_at_3']}/{hybrid_main['n']}",
                 "source": "results/hybrid_m1.json#/main/recall_at_3"},
                {"label": "MRR", "value": _fmt(hybrid_main["mrr"]),
                 "source": "results/hybrid_m1.json#/main/mrr"},
                {"label": "p50", "value": f"{hybrid_main['latency_ms_p50']} ms",
                 "source": "results/hybrid_m1.json#/main/latency_ms_p50"},
                {"label": "p95", "value": f"{hybrid_main['latency_ms_p95']} ms",
                 "source": "results/hybrid_m1.json#/main/latency_ms_p95"},
            ],
            "verdict": "真实规模上的主结果；只有 10 题，不能当生产指标。",
        },
        {
            "id": "dense",
            "title": "M2 真语义向量",
            "scope": f"{dense['corpus']['docs']} docs / {dense['corpus']['chunks']} chunks",
            "tone": "bad",
            "metrics": [
                {"label": "recall@3", "value": dense_main["recall_at_3"],
                 "source": "results/dense_m2.json#/main_dense_zh/recall_at_3"},
                {"label": "MRR", "value": _fmt(dense_main["mrr_at_3"]),
                 "source": "results/dense_m2.json#/main_dense_zh/mrr_at_3"},
                {"label": "p50", "value": f"{dense_main['latency_ms']['p50']} ms",
                 "source": "results/dense_m2.json#/main_dense_zh/latency_ms/p50"},
                {"label": "同轮稀疏 p50", "value": f"{sparse_same_run['latency_ms']['p50']} ms",
                 "source": "results/dense_m2.json#/main_sparse_m1cfg/latency_ms/p50"},
            ],
            "verdict": "没有赢稀疏融合，而且更慢；这是一个负结果，不是胜利。",
        },
        {
            "id": "metamorphic",
            "title": "M3 变异测试",
            "scope": f"{len(mrs)} MRs × {len(metamorphic['runs'][0]['cases'])} cases",
            "tone": "warn",
            "metrics": [
                {"label": "INVARIANT", "value": f"{comparison['INVARIANT']['before']} → {comparison['INVARIANT']['after']}",
                 "source": "results/metamorphic_m3.json#/comparison/INVARIANT"},
                {"label": "DESIRABLE", "value": f"{comparison['DESIRABLE']['before']} → {comparison['DESIRABLE']['after']}",
                 "source": "results/metamorphic_m3.json#/comparison/DESIRABLE"},
                {"label": "归一化修复", "value": comparison["INVARIANT"]["fixed_by_normalizer"] + comparison["DESIRABLE"]["fixed_by_normalizer"],
                 "source": "results/metamorphic_m3.json#/comparison/*/fixed_by_normalizer"},
            ],
            "verdict": "归一化修掉全部 INVARIANT；DESIRABLE 仍有剩余，不能宣称已解决。",
        },
    ]

    ablations = [
        {
            "id": "rerank",
            "title": "bigram 重排消融",
            "rows": [
                {"label": "on", "recall": rerank["on"]["recall_at_3"],
                 "mrr": rerank["on"]["mrr"]},
                {"label": "off", "recall": rerank["off"]["recall_at_3"],
                 "mrr": rerank["off"]["mrr"]},
            ],
            "delta_recall": rerank["delta_recall"],
            "note": "on/off 完全相同，delta_recall=0；重排在这组 query 上没有贡献。",
            "source": "results/hybrid_m1.json#/rerank_ablation",
        },
        {
            "id": "sweep",
            "title": "w_cos 权重扫描",
            "points": sweep,
            "best": best_sweep,
            "chosen": chosen_sweep,
            "note": (
                f"BM25-only (w_cos={best_sweep['w_cos']}) MRR {best_sweep['mrr']:.4f} "
                f"高于照搬的 w_cos={chosen_sweep['w_cos']} 的 {chosen_sweep['mrr']:.4f}；"
                "权重不能照搬。"
            ),
            "source": "results/hybrid_m1.json#/sweep",
        },
        {
            "id": "overlap",
            "title": "overlap 扫描",
            "points": overlap,
            "best": best_overlap,
            "chosen": chosen_overlap,
            "note": (
                f"overlap={best_overlap['overlap']} MRR {best_overlap['mrr']:.4f} "
                f"高于默认 overlap={chosen_overlap['overlap']} 的 {chosen_overlap['mrr']:.4f}；"
                "默认值不是最优。"
            ),
            "source": "results/hybrid_m1.json#/overlap_study",
        },
        {
            "id": "cutoff",
            "title": "候选截断扫描",
            "points": cutoff,
            "note": "candidates 从 10 到 500，recall 与 MRR 都没变；截断不是这组数据的瓶颈。",
            "source": "results/hybrid_m1.json#/cutoff_study",
        },
    ]

    findings = [
        f"M1 稀疏融合：{hybrid_main['recall_at_3']}/{hybrid_main['n']} recall@3，"
        f"MRR {hybrid_main['mrr']:.4f}，{hybrid_main['corpus_chunks']} chunks。",
        f"M2 dense：{dense_main['recall_at_3']} recall@3，MRR {dense_main['mrr_at_3']:.4f}；"
        f"同轮稀疏 p50 {sparse_same_run['latency_ms']['p50']} ms，dense p50 "
        f"{dense_main['latency_ms']['p50']} ms。",
        "bigram 重排 on/off 的 recall 与 MRR 完全相同，delta_recall=0。",
        f"w_cos 扫描的最佳点是 {best_sweep['w_cos']}（MRR {best_sweep['mrr']:.4f}），"
        f"不是照搬的 0.6（MRR {chosen_sweep['mrr']:.4f}）。",
        f"overlap 扫描的最佳点是 {best_overlap['overlap']}（MRR {best_overlap['mrr']:.4f}），"
        f"不是默认的 40（MRR {chosen_overlap['mrr']:.4f}）。",
        f"归一化修掉 {comparison['INVARIANT']['fixed_by_normalizer']} 条 INVARIANT 违规，"
        f"并把 DESIRABLE 从 {comparison['DESIRABLE']['before']} 降到 "
        f"{comparison['DESIRABLE']['after']}；仍有剩余。",
    ]

    refutes = [
        "题集只有 10 题，语料 537 docs / 11994 chunks；这不是生产基准。",
        "11994-chunk 语料来自私有姊妹仓，不在本仓；本 Demo 回放已提交结果，不重跑那份语料。",
        "冻结基线 5/5 是 7 docs / 10 chunks 的 toy，只证明链路跑通，不证明检索质量。",
        "dense 用的是中文 BGE，但题集含 1 条英文 query；语言不匹配是未分离的协变量。",
        "变异关系是手选的 6 条，不是穷尽集合；DESIRABLE 的剩余违规不能被“归一化”一句带过。",
    ]

    checks = []

    def check(name: str, actual, expected) -> None:
        checks.append({"name": name, "actual": actual,
                       "expected": expected, "ok": actual == expected})

    check("baseline.recall_at_3", baseline["recall_at_3"], "5/5")
    check("baseline.mrr", baseline["mrr"], 1.0)
    check("hybrid.recall_at_3", hybrid_main["recall_at_3"], 8)
    check("hybrid.mrr", hybrid_main["mrr"], 0.55)
    check("dense.recall_at_3", dense_main["recall_at_3"], "5/10")
    check("dense.mrr", dense_main["mrr_at_3"], 0.45)
    check("rerank.delta_recall", rerank["delta_recall"], 0)
    check("sweep.best_mrr", best_sweep["mrr"], 0.6333)
    check("overlap.best_mrr", best_overlap["mrr"], 0.625)
    check("metamorphic.invariant_after", comparison["INVARIANT"]["after"], 0)
    check("metamorphic.desirable_after", comparison["DESIRABLE"]["after"], 8)
    check("query_table.n", query_table["summary"]["n"], 10)
    check("query_table.sparse_hits", query_table["summary"]["sparse_hits"], 8)
    check("query_table.dense_hits", query_table["summary"]["dense_hits"], 5)
    check(
        "query_table.partition",
        sum(query_table["summary"][key]
            for key in ("both", "sparse_only", "dense_only", "neither")),
        10,
    )
    check("metamorphic_table.relations", len(metamorphic_table["rows"]), 6)
    check(
        "metamorphic_table.before",
        metamorphic_table["summary"]["before"],
        comparison["INVARIANT"]["before"] + comparison["DESIRABLE"]["before"],
    )
    check(
        "metamorphic_table.after",
        metamorphic_table["summary"]["after"],
        comparison["INVARIANT"]["after"] + comparison["DESIRABLE"]["after"],
    )
    check(
        "metamorphic_table.fixed",
        metamorphic_table["summary"]["fixed"],
        comparison["INVARIANT"]["fixed_by_normalizer"]
        + comparison["DESIRABLE"]["fixed_by_normalizer"],
    )
    check("baseline_examples.n", len(baseline_examples), 3)
    check(
        "baseline_examples.first_doc",
        baseline_examples[0]["results"][0]["doc_id"],
        "rag_overview",
    )

    mismatches = [c for c in checks if not c["ok"]]
    commit, dirty, dirty_paths = _git_snapshot()
    return {
        "meta": {
            "repo": "enterprise-rag",
            "demo": "retrieval-evidence",
            "commit": commit,
            "worktree_dirty": dirty,
            "dirty_paths": dirty_paths,
            "generated_at": generated_at,
            "mode": "result-replay+baseline-live",
            "python": sys.version.split()[0],
            "note": (
                "结果回放：私有 11994-chunk 语料不在仓内；"
                "/api/query 只跑 7-doc/10-chunk 冻结基线。"
            ),
        },
        "summary": {
            "baseline": {
                "recall": baseline["recall_at_3"], "mrr": baseline["mrr"],
                "docs": baseline["corpus_docs"], "chunks": baseline["corpus_chunks"],
            },
            "hybrid": {
                "recall": f"{hybrid_main['recall_at_3']}/{hybrid_main['n']}",
                "recall_val": hybrid_main["recall_rate"], "mrr": hybrid_main["mrr"],
                "docs": hybrid_main["corpus_docs"], "chunks": hybrid_main["corpus_chunks"],
            },
            "dense": {
                "recall": dense_main["recall_at_3"],
                "recall_val": dense_main["recall_at_3_val"],
                "mrr": dense_main["mrr_at_3"],
                "docs": dense["corpus"]["docs"], "chunks": dense["corpus"]["chunks"],
            },
            "metamorphic": {
                "invariant_before": comparison["INVARIANT"]["before"],
                "invariant_after": comparison["INVARIANT"]["after"],
                "desirable_before": comparison["DESIRABLE"]["before"],
                "desirable_after": comparison["DESIRABLE"]["after"],
                "fixed_by_normalizer": (
                    comparison["INVARIANT"]["fixed_by_normalizer"]
                    + comparison["DESIRABLE"]["fixed_by_normalizer"]
                ),
                "relations": len(mrs),
                "cases_per_run": len(metamorphic["runs"][0]["cases"]),
            },
            "rerank": {"delta_recall": rerank["delta_recall"],
                       "mrr_on": rerank["on"]["mrr"],
                       "mrr_off": rerank["off"]["mrr"]},
        },
        "layers": layers,
        "ablations": ablations,
        "query_table": query_table,
        "metamorphic_table": metamorphic_table,
        "baseline_examples": baseline_examples,
        "findings": findings,
        "refutes": refutes,
        "baseline_query": {
            "example": "RAG 由哪几部分组成",
            "scope": "7 docs / 10 chunks（冻结基线，不是 11994-chunk 结果）",
        },
        "sources": {
            "hybrid": "results/hybrid_m1.json",
            "dense": "results/dense_m2.json",
            "metamorphic": "results/metamorphic_m3.json",
            "baseline": "baseline/rag_demo.py",
        },
        "verification": {
            "status": "MATCH" if not mismatches else "MISMATCH",
            "checks": checks,
            "mismatches": [c["name"] for c in mismatches],
        },
    }


def write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
