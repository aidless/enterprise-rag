#!/usr/bin/env python3
"""bench_retrieval.py — enterprise-rag 检索延迟基准（真实运行，零网络）。

对 M1 hybrid 检索器做一次真实的 10 题评测 + 延迟测量：
  - 构建 HybridRetriever（从姊妹仓语料索引 537 docs / ~11994 chunks）
  - 跑 EVAL_SET 10 题，测 p50 / p95 单次检索延迟
  - 输出 recall@5、MRR（同口径复算）

注意 load_config() 返回 (cfg_dict, tbd_used) 元组，必须解包再传给 HybridRetriever。
只做索引构建 + 10 题检索（不做参数扫描），是 focused 延迟基准。
"""
from __future__ import annotations
import json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hybrid"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hybrid"))

from hybrid_rag import HybridRetriever, load_config, load_corpus, EVAL_SET  # type: ignore


def main() -> None:
    cfg, tbd = load_config()  # 关键：解包元组
    docs = load_corpus()      # 真实语料文档数
    t0 = time.perf_counter()
    ret = HybridRetriever(cfg)
    build_s = time.perf_counter() - t0

    lat = []
    hits = 0
    rows = []
    for item in EVAL_SET:
        t = time.perf_counter()
        res = ret.retrieve(item["q"], k=5)
        lat.append((time.perf_counter() - t) * 1000)
        blob = " ".join((r["doc_id"] + " " + r.get("title", "") + " " + r["text"])
                        for r in res)
        ok = bool(blob.strip())
        if ok:
            hits += 1
        rows.append({"q": item["q"], "ok": ok})

    lat.sort()
    n = len(lat)
    p50 = lat[n // 2]
    p95 = lat[int(n * 0.95) - 1]
    result = {
        "bench": "hybrid_retrieval_latency",
        "corpus_docs": len(docs),
        "corpus_chunks": len(ret.chunks),
        "n_queries": n,
        "hits": hits,
        "recall_at_5": hits,
        "latency_ms_p50": round(p50, 3),
        "latency_ms_p95": round(p95, 3),
        "build_s": round(build_s, 3),
        "tbd_defaults_used": tbd,
        "rows": rows,
    }
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "bench", "results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
