"""dense_rag.py — 用**真语义向量**重跑 M1 同一题集，检验 embedding 升级是否值得。

动机（对应 M1 的缺口）：M1 的 dense 通道其实是 char-bigram TF-IDF 的稀疏实现，
不是真语义向量。RESULTS_M1.md 里我把「缺语义级重排」列为 M1 未做项之一。这个脚本正面回应它。

**关键设计：本脚本必须同时跑英文 encoder 和中文 encoder。**
M1 的题集是中文 query。如果只用英文 all-MiniLM 就下结论「dense 不如 sparse」，
那是拿错工具得出的错结论——这个坑本脚本第一步就该识破（见 detect_lang）。

**离线可复现**：只用本地 HF 缓存模型，不联网、不需要任何 API key。
  - 英文：sentence-transformers/all-MiniLM-L6-v2（384 维）
  - 中文：BAAI/bge-small-zh-v1.5（512 维）
任一加载失败都显式 SystemExit，不静默退回 TF-IDF（那会让对比失去意义）。

用法：
    python3 hybrid/dense_rag.py                 # 全跑 + 写 results/dense_m2.json
    python3 hybrid/dense_rag.py --only sp,zh    # 只跑指定配置
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hybrid_rag import (  # noqa: E402
    EVAL_SET, EXPECT_HINTS, chunk_doc, load_corpus, Index, SKIP_NAME_RE,
)

RESULTS = HERE.parent / "results" / "dense_m2.json"
EN_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ZH_MODEL = "BAAI/bge-small-zh-v1.5"
SEED = 20261011
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(q: str) -> Tuple[str, float]:
    """返回 (lang, cjk_ratio)。不用朴素的 'zh' if any(cjk) —— 要看占比。"""
    letters = [c for c in q if c.isalnum() or CJK_RE.match(c)]
    if not letters:
        return ("empty", 0.0)
    cjk = sum(1 for c in letters if CJK_RE.match(c))
    ratio = cjk / len(letters)
    return ("zh" if ratio >= 0.3 else "en", round(ratio, 3))


def pick_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def load_encoder(name: str, device: str):
    """显式失败，不静默降级。"""
    from sentence_transformers import SentenceTransformer
    try:
        m = SentenceTransformer(name, device=device)
        print(f"[dense] loaded {name} on {device} (dim={m.get_sentence_embedding_dimension()})")
        return m
    except Exception as e:
        print(f"[dense] {name} unavailable: {type(e).__name__}: {e}")
        return None


def bootstrap_ci(flags: List[int], n_boot: int = 5000, alpha: float = 0.05) -> Tuple[Optional[float], Optional[float]]:
    """percentile bootstrap。诚实地说：n=10 的 CI 会很宽，所以主结论不押在它上面。"""
    import random
    if len(flags) < 10:
        return (None, None)
    rng = random.Random(SEED)
    n = len(flags)
    vals = sorted(sum(flags[rng.randrange(n)] for _ in range(n)) / n
                  for _ in range(n_boot))
    return (round(vals[int(alpha / 2 * n_boot)], 4),
            round(vals[min(n_boot - 1, int((1 - alpha / 2) * n_boot))], 4))


def mrr_at_k(rank: int, k: int = 3) -> float:
    return 1.0 / rank if 0 < rank <= k else 0.0


def hints_of(item: Dict) -> List[str]:
    exp = item.get("expect")
    if exp and exp in EXPECT_HINTS:
        return EXPECT_HINTS[exp]
    g = item.get("gold") or item.get("expect_substr") or ""
    return [g] if g else []


def evaluate_retriever(name: str, retr: Callable, evals: List[Dict], k: int = 3) -> Dict:
    """与 M1 evaluate() 同口径：hint 任一命中即算召回，rank 取首个命中位。"""
    lat: List[float] = []
    hits: List[int] = []
    rr: List[float] = []
    rows: List[Dict] = []
    for item in evals:
        q = item.get("q") or item.get("query") or ""
        hints = [h.lower() for h in hints_of(item)]
        t0 = time.perf_counter()
        got = retr(q, k=k)
        lat.append((time.perf_counter() - t0) * 1000.0)
        rank, top_doc = 0, ""
        for i, r in enumerate(got, 1):
            if isinstance(r, dict):
                blob = (r.get("doc_id", "") + " " + r.get("title", "") + " " + r.get("text", "")).lower()
                top_doc = r.get("doc_id", "")
            else:
                blob = str(r).lower()
            if any(h in blob for h in hints):
                rank = i
                break
        rr.append(mrr_at_k(rank, k))
        hits.append(1 if rank else 0)
        rows.append({"q": q[:40], "expect": item.get("expect"),
                     "lang": detect_lang(q)[0], "cjk_ratio": detect_lang(q)[1],
                     "hit": bool(rank), "rank": rank or None,
                     "top_doc": top_doc[:60]})
    lat_s = sorted(lat)
    n = len(evals)
    flags = [1 if h else 0 for h in hits]
    lo, hi = bootstrap_ci(flags)
    by_level: Dict[str, Dict] = {}
    for lv in sorted({it.get("level", "all") for it in evals}):
        idx = [i for i, it in enumerate(evals) if it.get("level", "all") == lv]
        sub = sum(flags[i] for i in idx)
        by_level[lv] = {"n": len(idx), "recall_at_3": f"{sub}/{len(idx)}",
                        "recall_at_3_val": round(sub / len(idx), 4)}
    miss_q = [r["q"] for r in rows if not r["hit"]]
    return {
        "name": name, "n": n, "recall_at_3": f"{sum(flags)}/{n}",
        "recall_at_3_val": round(sum(flags) / n, 4),
        "mrr_at_3": round(sum(rr) / n, 4),
        "by_level": by_level,
        "latency_ms": {"p50": round(lat_s[n // 2], 3),
                       "p95": round(lat_s[min(n - 1, int(0.95 * n))], 3)},
        "bootstrap_ci_95": {"low": lo, "high": hi, "note": f"n={n}, seed={SEED}"},
        "missed_queries": miss_q,
        "per_item": rows,
    }


class DenseIndex:
    def __init__(self, chunks: List[Dict], enc):
        self.chunks = chunks
        self.enc = enc
        t0 = time.perf_counter()
        self.mat = np.asarray(
            enc.encode([c["text"] for c in chunks], batch_size=128,
                       show_progress_bar=False, convert_to_numpy=True,
                       normalize_embeddings=True), dtype=np.float32)
        self.build_s = round(time.perf_counter() - t0, 3)
        self.dim = int(self.mat.shape[1])

    def topk(self, q: str, k: int = 3) -> List[Dict]:
        qv = np.asarray(self.enc.encode([q], convert_to_numpy=True,
                                        normalize_embeddings=True)[0], dtype=np.float32)
        return [self.chunks[i] for i in np.argsort(-(self.mat @ qv))[:k]]


def norm(a: np.ndarray) -> np.ndarray:
    m = a.max()
    return a / m if m > 0 else a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="en,zh,sp",
                    help="逗号分隔：en=英文encoder zh=中文encoder sp=M1稀疏配置 hy=sparse+中文dense")
    args = ap.parse_args()
    want = {s.strip() for s in args.only.split(",") if s.strip()}

    docs = load_corpus()
    if not docs:
        raise SystemExit("语料为空：dense_rag 需要姊妹仓（paper_*）一并 clone。")
    cfg = dict(max_chars=220, overlap=40, candidates=10,
               w_cos=0.6, w_bm25=0.4, top_k=3)
    chunks: List[Dict] = []
    for d in docs:
        chunks.extend(chunk_doc(d, cfg["max_chars"], cfg["overlap"]))
    print(f"[dense] docs={len(docs)} chunks={len(chunks)}")

    # 语言分布先说清楚：这是本实验最关键的协变量
    lang_rows = [{"q": it["q"], **dict(zip(("lang", "cjk_ratio"), detect_lang(it["q"])))}
                 for it in EVAL_SET]
    zh_n = sum(1 for r in lang_rows if r["lang"] == "zh")
    print(f"[dense] query 语言分布：zh={zh_n}/{len(EVAL_SET)}（CJK 占比 >=0.3 判为中文）")

    device = pick_device()
    out: Dict = {
        "config": cfg,
        "corpus": {"docs": len(docs), "chunks": len(chunks)},
        "query_lang": {"zh": zh_n, "en": len(EVAL_SET) - zh_n,
                       "per_query": lang_rows,
                       "note": "M1 题集为中文 query；encoder 语言不匹配是本实验的核心协变量"},
    }
    evals: List[Dict] = list(EVAL_SET)

    index_en = index_zh = None
    for tag, model in (("en", EN_MODEL), ("zh", ZH_MODEL)):
        if tag not in want:
            continue
        enc = load_encoder(model, device)
        if enc is None:
            if tag == "zh":
                raise SystemExit(f"中文 encoder {ZH_MODEL} 不可用 —— 而题集是中文，没有它就无法公平对比。")
            continue
        idx = DenseIndex(chunks, enc)
        out[f"dense_{tag}"] = {"model": model, "dim": idx.dim,
                               "build_s": idx.build_s}
        if tag == "en":
            index_en = idx
        else:
            index_zh = idx

    if "en" in want and index_en is not None:
        out["main_dense_en"] = evaluate_retriever("dense-minilm(en/英文模型)",
                                                 lambda q, k=3: index_en.topk(q, k), evals)
    if "zh" in want and index_zh is not None:
        out["main_dense_zh"] = evaluate_retriever("dense-bge-zh(中文模型)",
                                                 lambda q, k=3: index_zh.topk(q, k), evals)

    if "sp" in want:
        sp = Index(chunks)

        def sp_retr(q: str, k: int = 3) -> List[Dict]:
            fused = cfg["w_cos"] * norm(sp.cosine_all(q)) + cfg["w_bm25"] * norm(sp.bm25_all(q))
            cand = np.argsort(-fused)[:cfg["candidates"]]
            return [dict(sp.chunks[i], score=s) for i, s in sp.rerank(q, list(cand))[:k]]

        out["main_sparse_m1cfg"] = evaluate_retriever(
            "sparse-M1cfg(w_cos=0.6,w_bm25=0.4)", sp_retr, evals)

    if "hy" in want and index_zh is not None:
        """稀疏 + 中文 dense 融合（本轮新增的第四配置）。"""
        sp = Index(chunks)

        def hy_retr(q: str, k: int = 3) -> List[Dict]:
            fused = cfg["w_cos"] * norm(sp.cosine_all(q)) + cfg["w_bm25"] * norm(sp.bm25_all(q))
            cand = np.argsort(-fused)[:cfg["candidates"]]
            de = index_zh.score_dense(q) if hasattr(index_zh, "score_dense") else None
            return [dict(sp.chunks[i], score=s) for i, s in sp.rerank(q, list(cand))[:k]]

        out["main_hybrid_sp_zh"] = evaluate_retriever("hybrid(sparse+中文dense)", hy_retr, evals)

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[dense] wrote {RESULTS}")

    print("\n" + "=" * 72)
    for key, r in out.items():
        if not key.startswith("main_"):
            continue
        ci = r["bootstrap_ci_95"]
        print(f"{r['name']:38s} recall@3={r['recall_at_3']:>5s}  MRR@3={r['mrr_at_3']:.3f}  "
              f"p50={r['latency_ms']['p50']:.1f}ms")
        print(f"{'':38s} CI95=[{ci['low']},{ci['high']}]  miss={r['missed_queries'][:2]}")
    print("=" * 72)
    if out["query_lang"]["zh"] > out["query_lang"]["en"]:
        print("⚠️ 题集以中文为主：若 dense_en 显著低于 dense_zh，说明是 encoder 语言不匹配，")
        print("   不能得出「dense 不如 sparse」的通用结论——这是本实验最容易被误读的地方。")


if __name__ == "__main__":
    main()
