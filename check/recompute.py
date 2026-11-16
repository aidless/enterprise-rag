#!/usr/bin/env python3
"""Recompute published retrieval metrics from committed per-question rows.

This module does not re-index the sister corpus and does not load bge.
`make check` uses it to prove the README evidence block matches the JSON,
and to re-run the in-repo 7-document baseline.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- EVIDENCE:BEGIN -->"
END = "<!-- EVIDENCE:END -->"
SEED = 20261011
N_BOOT = 5000
HARDWARE = "hardware: not recorded in this file"

# Phrases that have already been false relative to the committed tree.
# A line that starts with "Observed (false)" may quote them.
FORBIDDEN = (
    "allow-number",
    "3.25ms",
    "3.25 ms",
    "8.40ms",
    "8.40 ms",
    "p50 3-4",
    "0.88s",
    "0.88 s",
    "12000",
    "MRR 0.10",
    "spec-only",
    "Spec only, no code",
    "A design specification with no code",
    "不含任何实现代码",
    "零核心检索代码",
    "无数据文件",
    "无可执行验证",
)

SCAN_FILES = (
    "README.md",
    "STATUS.md",
    "PREREG.md",
    "CONTRIBUTING.md",
    "FAILURE_MODES.md",
    "results/README.md",
    "hybrid/README.md",
    "hybrid/RESULTS_M1.md",
    "BLINE_REPORT.md",
    "golden/README.md",
    "latency/README.md",
    "harness/README.md",
    "reranker/README.md",
    ".github/workflows/ci.yml",
    ".github/workflows/pr-checks.yml",
    "demo/README.md",
)

OBSERVED_ABOUT = (
    "混合检索企业 RAG（BM25+向量）的设计文档：含评测指标方案；"
    "spec-only，仓库当前不含任何实现代码。"
)


def fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return f"{value:.1f}"
        return format(value, ".10g")
    return str(value)


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def bootstrap_mean(values: list[float], n_boot: int = N_BOOT, alpha: float = 0.05,
                   seed: int = SEED) -> tuple[float, float]:
    """Percentile bootstrap. Same index rule as hybrid/dense_rag.py bootstrap_ci."""
    if len(values) < 10:
        raise ValueError(f"bootstrap requires n>=10, got {len(values)}")
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(n_boot)
    )
    lo = round(samples[int(alpha / 2 * n_boot)], 4)
    hi = round(samples[min(n_boot - 1, int((1 - alpha / 2) * n_boot))], 4)
    return lo, hi


def strict_at_3(rows: list[dict], hit_key: str, rank_key: str = "rank") -> tuple[int, float, int]:
    hits = 0
    rr = 0.0
    max_rank = 0
    for row in rows:
        rank = row.get(rank_key)
        hit = bool(row.get(hit_key))
        if hit:
            if not isinstance(rank, int) or rank < 1:
                raise ValueError(f"hit row missing rank: {row.get('q')}")
            if rank <= 3:
                hits += 1
                rr += 1.0 / rank
            max_rank = max(max_rank, rank)
        elif rank not in (None, 0):
            raise ValueError(f"miss row has rank: {row.get('q')} rank={rank}")
    return hits, rr / len(rows), max_rank


def recount_metamorphic(payload: dict) -> dict:
    out = {}
    for run in payload["runs"]:
        counts = {}
        for case in run["cases"]:
            bucket = counts.setdefault(case["class"], {"n": 0, "violations": 0})
            bucket["n"] += 1
            bucket["violations"] += int(bool(case["violation"]))
        out[run["tag"]] = counts
    return out


def about_replacement(n: int) -> str:
    text = (
        f"Local research repo: sparse vs dense retrieval on one {n}-question set, "
        "with committed results. Not production and not enterprise-ready. "
        f"n={n}, no significance claim. golden/latency/harness/reranker are empty contracts."
    )
    if len(text) > 350:
        raise ValueError("GitHub About replacement exceeds 350 characters")
    return text


def evidence_facts() -> dict:
    hybrid = load_json("results/hybrid_m1.json")
    dense = load_json("results/dense_m2.json")
    meta = load_json("results/metamorphic_m3.json")
    bench = load_json("bench/results.json")
    main = hybrid["main"]
    sparse = dense["main_sparse_m1cfg"]
    dense_arm = dense["main_dense_zh"]
    h_hits, h_mrr, h_max = strict_at_3(main["rows"], "ok")
    s_hits, s_mrr, s_max = strict_at_3(sparse["per_item"], "hit")
    d_hits, d_mrr, d_max = strict_at_3(dense_arm["per_item"], "hit")
    if [r["q"] for r in sparse["per_item"]] != [r["q"] for r in dense_arm["per_item"]]:
        raise ValueError("dense and sparse per_item questions are not aligned")
    if [r["q"] for r in main["rows"]] != [r["q"] for r in sparse["per_item"]]:
        raise ValueError("hybrid_m1 rows are not aligned with dense_m2 sparse per_item")
    sparse_flags = [1.0 if r["hit"] else 0.0 for r in sparse["per_item"]]
    dense_flags = [1.0 if r["hit"] else 0.0 for r in dense_arm["per_item"]]
    paired = [s - d for s, d in zip(sparse_flags, dense_flags)]
    sparse_rr = [
        (1.0 / r["rank"]) if r["hit"] and r["rank"] and r["rank"] <= 3 else 0.0
        for r in sparse["per_item"]
    ]
    dense_rr = [
        (1.0 / r["rank"]) if r["hit"] and r["rank"] and r["rank"] <= 3 else 0.0
        for r in dense_arm["per_item"]
    ]
    best_sweep = max(hybrid["sweep"], key=lambda r: (r["mrr"], r["recall_at_3"]))
    best_overlap = max(hybrid["overlap_study"], key=lambda r: (r["mrr"], r["recall_at_3"]))
    recounted = recount_metamorphic(meta)
    return {
        "hybrid": hybrid,
        "dense": dense,
        "meta": meta,
        "bench": bench,
        "main": main,
        "sparse": sparse,
        "dense_arm": dense_arm,
        "h_hits": h_hits,
        "h_mrr": h_mrr,
        "h_max": h_max,
        "s_hits": s_hits,
        "s_mrr": s_mrr,
        "s_max": s_max,
        "d_hits": d_hits,
        "d_mrr": d_mrr,
        "d_max": d_max,
        "sparse_ci": bootstrap_mean(sparse_flags),
        "dense_ci": bootstrap_mean(dense_flags),
        "paired_ci": bootstrap_mean(paired),
        "paired_mean": sum(paired) / len(paired),
        "sparse_mrr_ci": bootstrap_mean(sparse_rr),
        "dense_mrr_ci": bootstrap_mean(dense_rr),
        "best_sweep": best_sweep,
        "best_overlap": best_overlap,
        "recounted": recounted,
    }


def assert_json_consistent(facts: dict) -> list[str]:
    errors = []
    main = facts["main"]
    if facts["h_hits"] != main["recall_at_3"] or main["n"] != len(main["rows"]):
        errors.append(
            f"hybrid_m1 recall_at_3 {main['recall_at_3']} != strict top-3 recount {facts['h_hits']}"
        )
    if abs(facts["h_mrr"] - main["mrr"]) > 1e-9:
        errors.append(f"hybrid_m1 mrr {main['mrr']} != recount {facts['h_mrr']}")
    if facts["h_max"] > 3:
        errors.append(f"hybrid_m1 has a hit rank {facts['h_max']} above 3")
    for label, block, hits, mrr in (
        ("sparse", facts["sparse"], facts["s_hits"], facts["s_mrr"]),
        ("dense", facts["dense_arm"], facts["d_hits"], facts["d_mrr"]),
    ):
        if hits != int(block["recall_at_3"].split("/")[0]) or block["n"] != 10:
            errors.append(f"{label} recall {block['recall_at_3']} != recount {hits}/10")
        if abs(mrr - block["mrr_at_3"]) > 1e-9:
            errors.append(f"{label} mrr {block['mrr_at_3']} != recount {mrr}")
        stored = block["bootstrap_ci_95"]
        ci = facts["sparse_ci"] if label == "sparse" else facts["dense_ci"]
        if abs(ci[0] - stored["low"]) > 5e-5 or abs(ci[1] - stored["high"]) > 5e-5:
            errors.append(f"{label} bootstrap {ci} != committed {stored}")
        if "seed=20261011" not in stored.get("note", ""):
            errors.append(f"{label} bootstrap note missing seed=20261011")
    comp = facts["meta"]["comparison"]
    recounted = facts["recounted"]
    for tag, before_key in (("before_normalizer", "before"), ("after_normalizer", "after")):
        for klass in ("INVARIANT", "DESIRABLE"):
            got = recounted[tag][klass]["violations"]
            want = comp[klass][before_key]
            if got != want:
                errors.append(f"metamorphic {klass} {tag} recount {got} != comparison {want}")
    producer = (ROOT / "hybrid" / "hybrid_rag.py").read_text(encoding="utf-8")
    if 'retrieve(item["q"], k=5)' not in producer:
        errors.append("hybrid evaluate() no longer calls retrieve(..., k=5); reread recall_at_3")
    if '"cooking": ["python3", "main.py"]' not in producer:
        errors.append("cooking hint changed; update FAILURE_MODES before trusting the old label")
    bench_src = (ROOT / "bench" / "bench_retrieval.py").read_text(encoding="utf-8")
    if "ok = bool(blob.strip())" not in bench_src:
        errors.append("bench hit definition changed; do not describe recall_at_5 until rewritten")
    frozen = facts["hybrid"]["baseline_frozen"]
    if frozen["recall_at_3"] != "5/5" or frozen["corpus_docs"] != 7 or frozen["corpus_chunks"] != 10:
        errors.append("baseline_frozen block does not match the in-repo 7-doc/10-chunk claim")
    return errors


def _overlap_clause(sparse_ci: tuple[float, float], dense_ci: tuple[float, float]) -> str:
    if sparse_ci[0] <= dense_ci[1] and dense_ci[0] <= sparse_ci[1]:
        return "The intervals overlap."
    return (
        "The intervals do not overlap. That is still not a significance test "
        "on ten questions that were also used for tuning."
    )


def render_evidence(facts: dict | None = None) -> str:
    facts = facts or evidence_facts()
    main = facts["main"]
    sparse = facts["sparse"]
    dense_arm = facts["dense_arm"]
    model = facts["dense"]["dense_zh"]["model"]
    s_lo, s_hi = facts["sparse_ci"]
    d_lo, d_hi = facts["dense_ci"]
    p_lo, p_hi = facts["paired_ci"]
    sm_lo, sm_hi = facts["sparse_mrr_ci"]
    dm_lo, dm_hi = facts["dense_mrr_ci"]
    lines = [
        (
            f"On the one {main['n']}-question set in `results/hybrid_m1.json` and "
            f"`results/dense_m2.json`, sparse fusion recall@3 is {facts['h_hits']}/{main['n']} "
            f"(MRR {fmt(main['mrr'])}) and `{model}` recall@3 is {facts['d_hits']}/{dense_arm['n']} "
            f"(MRR@3 {fmt(dense_arm['mrr_at_3'])})."
        ),
        (
            f"That comparison is this corpus snapshot only ({main['corpus_docs']} documents / "
            f"{main['corpus_chunks']} chunks) and this question set. It is not a generalization "
            "result and it is not an enterprise-readiness result."
        ),
        (
            f"With only those {main['n']} questions, recall bootstrap 95% intervals are sparse "
            f"{fmt(s_lo)}–{fmt(s_hi)} and dense {fmt(d_lo)}–{fmt(d_hi)} "
            f"(seed {SEED}, {N_BOOT} resamples, recomputed from the per-question hits). "
            f"{_overlap_clause(facts['sparse_ci'], facts['dense_ci'])} "
            "This repository does not claim that sparse beats dense."
        ),
        "",
        "## Published sparse result (`results/hybrid_m1.json`)",
        "",
        (
            f"Strict top-3 recount from `main.rows`: recall {facts['h_hits']}/{main['n']}, "
            f"MRR {fmt(facts['h_mrr'])}, max hit rank {facts['h_max']}. "
            f"Stored fields: recall_at_3 {main['recall_at_3']}, mrr {fmt(main['mrr'])}, "
            f"recall_rate {fmt(main['recall_rate'])}, corpus {main['corpus_docs']} / {main['corpus_chunks']}."
        ),
        (
            "`hybrid/hybrid_rag.py` `evaluate()` calls `retrieve(..., k=5)` while the field is named "
            "recall_at_3. In this file every recorded hit rank is <= 3, so the strict top-3 recount "
            "equals the stored field. The name and the call are not the same definition."
        ),
        (
            f"Stored latency on this run: p50 {fmt(main['latency_ms_p50'])} ms, "
            f"p95 {fmt(main['latency_ms_p95'])} ms. {HARDWARE}."
        ),
        (
            f"Same-set sweeps, not held-out tests: best `sweep` row is w_cos {fmt(facts['best_sweep']['w_cos'])} "
            f"with MRR {fmt(facts['best_sweep']['mrr'])}; the reported main config is w_cos "
            f"{fmt(facts['hybrid']['config']['w_cos'])}. Best `overlap_study` row is overlap "
            f"{facts['best_overlap']['overlap']} with MRR {fmt(facts['best_overlap']['mrr'])}. "
            f"`rerank_ablation.delta_recall` is {facts['hybrid']['rerank_ablation']['delta_recall']}."
        ),
        "",
        "## Same questions, dense arm (`results/dense_m2.json`)",
        "",
        (
            f"Model `{model}`, dim {facts['dense']['dense_zh']['dim']}, "
            f"build_s {fmt(facts['dense']['dense_zh']['build_s'])}. "
            f"Dense strict top-3 recount {facts['d_hits']}/{dense_arm['n']}, MRR {fmt(facts['d_mrr'])} "
            f"(stored {dense_arm['recall_at_3']}, MRR@3 {fmt(dense_arm['mrr_at_3'])}). "
            f"Sparse arm in this file: {facts['s_hits']}/{sparse['n']}, MRR {fmt(facts['s_mrr'])} "
            f"(stored {sparse['recall_at_3']}, MRR@3 {fmt(sparse['mrr_at_3'])})."
        ),
        (
            f"Stored latency in this file, sparse arm p50 {fmt(sparse['latency_ms']['p50'])} ms / "
            f"p95 {fmt(sparse['latency_ms']['p95'])} ms; dense arm p50 {fmt(dense_arm['latency_ms']['p50'])} ms / "
            f"p95 {fmt(dense_arm['latency_ms']['p95'])} ms. {HARDWARE}. "
            "A ratio of those two p50 fields is not stored, and this block does not add one. "
            "Do not substitute `hybrid_m1.json` p50 for the sparse p50 in this file; it is a different stored timing."
        ),
        (
            "No English-encoder metrics are in this file. `hybrid/dense_rag.py` names "
            "`sentence-transformers/all-MiniLM-L6-v2`, and running that path requires the model "
            "already on disk. This block does not cite an English-encoder score."
        ),
        "",
        "| question | sparse rank | dense rank |",
        "| --- | --- | --- |",
    ]
    for sp, de in zip(sparse["per_item"], dense_arm["per_item"]):
        def _rank(row: dict) -> str:
            return str(row["rank"]) if row["hit"] else "miss"
        lines.append(f"| {sp['q']} | {_rank(sp)} | {_rank(de)} |")
    lines += [
        "",
        "## Bootstrap recomputed from those rows",
        "",
        (
            f"Recall, same algorithm as `hybrid/dense_rag.py` `bootstrap_ci` "
            f"(seed {SEED}, {N_BOOT} resamples): sparse {fmt(s_lo)}–{fmt(s_hi)} "
            f"(committed {fmt(sparse['bootstrap_ci_95']['low'])}–{fmt(sparse['bootstrap_ci_95']['high'])}); "
            f"dense {fmt(d_lo)}–{fmt(d_hi)} "
            f"(committed {fmt(dense_arm['bootstrap_ci_95']['low'])}–{fmt(dense_arm['bootstrap_ci_95']['high'])})."
        ),
        (
            f"MRR bootstrap is not stored in the JSON. Recomputed here from per-question reciprocal rank: "
            f"sparse {fmt(sm_lo)}–{fmt(sm_hi)}, dense {fmt(dm_lo)}–{fmt(dm_hi)}."
        ),
        (
            f"Paired (sparse hit − dense hit) mean {fmt(round(facts['paired_mean'], 4))}, "
            f"bootstrap 95% interval {fmt(p_lo)}–{fmt(p_hi)}. "
            "This is a description of these ten paired rows, not a significance test."
        ),
        "",
        "## Metamorphic (`results/metamorphic_m3.json`)",
        "",
        (
            f"Recounted INVARIANT violations: "
            f"{facts['recounted']['before_normalizer']['INVARIANT']['violations']} before, "
            f"{facts['recounted']['after_normalizer']['INVARIANT']['violations']} after "
            f"(comparison block {facts['meta']['comparison']['INVARIANT']['before']} → "
            f"{facts['meta']['comparison']['INVARIANT']['after']}). "
            f"DESIRABLE violations: "
            f"{facts['recounted']['before_normalizer']['DESIRABLE']['violations']} before, "
            f"{facts['recounted']['after_normalizer']['DESIRABLE']['violations']} after "
            f"(rate after {fmt(facts['meta']['comparison']['DESIRABLE']['after_rate'])}). "
            "DESIRABLE failures are still failures of those relations; the normalizer did not clear them."
        ),
        "",
        "## Latency snapshot that is not gold recall (`bench/results.json`)",
        "",
        (
            f"Stored corpus {facts['bench']['corpus_docs']} / {facts['bench']['corpus_chunks']}, "
            f"p50 {fmt(facts['bench']['latency_ms_p50'])} ms, "
            f"p95 {fmt(facts['bench']['latency_ms_p95'])} ms, "
            f"build_s {fmt(facts['bench']['build_s'])}. {HARDWARE}. "
            f"The field recall_at_5 is {facts['bench']['recall_at_5']}. "
            "`bench/bench_retrieval.py` sets it with `ok = bool(blob.strip())`, "
            "which is true when retrieval returns any text. It is not gold-document recall "
            f"and it is not comparable to the {facts['h_hits']}/{main['n']} above."
        ),
        "",
        "## In-repo baseline",
        "",
        (
            f"`baseline_frozen` in `hybrid_m1.json`: recall@3 {facts['hybrid']['baseline_frozen']['recall_at_3']}, "
            f"MRR {fmt(facts['hybrid']['baseline_frozen']['mrr'])}, "
            f"{facts['hybrid']['baseline_frozen']['corpus_docs']} documents / "
            f"{facts['hybrid']['baseline_frozen']['corpus_chunks']} chunks. "
            "`make check` re-runs `baseline/rag_demo.py` and requires the printed "
            "`recall@3 = 5/5` and `MRR = 1.000`. That re-run is the sparse retrieval this clone can execute."
        ),
    ]
    return "\n".join(lines)


def scan_lines(path: str, lines: list[str]) -> list[str]:
    errors = []
    for lineno, line in enumerate(lines, 1):
        if line.strip().startswith("Observed (false)"):
            continue
        for phrase in FORBIDDEN:
            if phrase in line:
                errors.append(f"{path}:{lineno}: forbidden phrase {phrase!r}")
    return errors


def scan_tree() -> list[str]:
    errors = []
    for rel in SCAN_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        errors.extend(scan_lines(rel, path.read_text(encoding="utf-8").splitlines()))
    return errors


def readme_block_errors(rendered: str) -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return ["README.md is missing EVIDENCE markers"]
    middle = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if middle != rendered.strip():
        return ["README.md evidence block does not match check/recompute.py render_evidence()"]
    statement = []
    for line in middle.splitlines():
        if not line.strip():
            if statement:
                break
            continue
        if line.startswith("#"):
            break
        statement.append(line)
    if len(statement) != 3:
        return [f"problem statement is {len(statement)} lines, expected 3"]
    return []


def contract_dir_errors() -> list[str]:
    errors = []
    for name in ("golden", "latency", "harness", "reranker"):
        directory = ROOT / name
        files = sorted(p.name for p in directory.iterdir() if p.name != ".gitkeep")
        if files != ["README.md"]:
            errors.append(f"{name}/ is not an empty contract: {files}")
            continue
        first = (directory / "README.md").read_text(encoding="utf-8").splitlines()[0]
        if not first.startswith("EMPTY CONTRACT"):
            errors.append(f"{name}/README.md does not start with EMPTY CONTRACT")
    return errors


def failure_mode_errors(facts: dict) -> list[str]:
    path = ROOT / "FAILURE_MODES.md"
    if not path.is_file():
        return ["FAILURE_MODES.md is missing"]
    text = path.read_text(encoding="utf-8")
    after = facts["meta"]["comparison"]["DESIRABLE"]["after"]
    before = facts["meta"]["comparison"]["INVARIANT"]["before"]
    required = (
        "tiny eval set",
        "question leakage",
        "char-bigram",
        "python3",
        "main.py",
        f"DESIRABLE violations after normalizer: {after}",
        f"INVARIANT violations before normalizer: {before}",
        "EMPTY CONTRACT",
        "hardware: not recorded",
        "ok = bool(blob.strip())",
        "retrieve(..., k=5)",
        "sister corpus",
        "GitHub About",
        "paper_workflow_kb",
        "no significance claim",
    )
    return [f"FAILURE_MODES.md missing {item!r}" for item in required if item not in text]


def about_errors() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    facts_n = evidence_facts()["main"]["n"]
    replacement = about_replacement(facts_n)
    errors = []
    if replacement not in text:
        errors.append("README.md missing the GitHub About replacement text")
    observed_line = f"Observed (false): {OBSERVED_ABOUT}"
    if observed_line not in text:
        errors.append("README.md missing the observed GitHub About line")
    if "chromadb" not in text:
        errors.append("README.md does not mention the stale chromadb topic")
    if "make check" not in text:
        errors.append("README.md does not document make check")
    if "BAAI/bge-small-zh-v1.5" not in text:
        errors.append("README.md does not state the bge model make check will not download")
    return errors


def ci_errors() -> list[str]:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pr = (ROOT / ".github" / "workflows" / "pr-checks.yml").read_text(encoding="utf-8")
    errors = []
    if "make check" not in ci:
        errors.append("ci.yml does not run make check")
    if "make check" not in pr:
        errors.append("pr-checks.yml does not run make check")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    if "recompute.py --check" not in makefile:
        errors.append("Makefile check target does not run the evidence check")
    return errors


def rerun_baseline() -> list[str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "baseline" / "rag_demo.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return [f"baseline/rag_demo.py exited {proc.returncode}: {proc.stderr[-400:]}"]
    if "recall@3 = 5/5" not in proc.stdout or "MRR = 1.000" not in proc.stdout:
        return ["baseline/rag_demo.py did not print recall@3 = 5/5 and MRR = 1.000"]
    return []


def collect_errors() -> list[str]:
    facts = evidence_facts()
    rendered = render_evidence(facts)
    return [
        *assert_json_consistent(facts),
        *readme_block_errors(rendered),
        *scan_tree(),
        *contract_dir_errors(),
        *failure_mode_errors(facts),
        *about_errors(),
        *ci_errors(),
        *rerun_baseline(),
    ]


def write_block() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit("README.md is missing EVIDENCE markers")
    pre, rest = text.split(BEGIN, 1)
    _, post = rest.split(END, 1)
    block = render_evidence().strip()
    path.write_text(pre + BEGIN + "\n" + block + "\n" + END + post, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when evidence drifts")
    parser.add_argument("--write", action="store_true", help="rewrite the README evidence block")
    args = parser.parse_args(argv)
    if args.write:
        write_block()
        print("wrote README evidence block")
        return 0
    errors = collect_errors()
    if errors:
        print(f"{len(errors)} evidence check(s) failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1
    print("evidence check passed (row recount, README block, baseline re-run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
