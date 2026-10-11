#!/usr/bin/env python3
"""metamorphic_test.py — 对 hybrid 检索做**变异测试**（M3-B）

为什么做这个：recall/MRR 只能说"平均有多好"，说不出"在什么输入下会坏"。
变异测试的思路反过来——不比较"对错"，而是声明一组** metamorphic relation**：
"把 query 做一个语义保持的变换后，结果应该不变/不应该显著变差"。
任何违反都定位到一个具体的 (原query, 变换后query) 对，可以直接复现。

关系分两类，避免把"模型的固有属性"误判成 bug：

  INVARIANT（必须成立，违反 = 缺陷）
    MR-1 determinism  同 query 两次检索，top-1 与分数完全一致
    MR-2 whitespace   在词间/首尾增加空白，top-1 不变
    MR-3 casewidth    ASCII 大小写互换、全角转半角，top-1 不变

  DESIRABLE（不一定成立，违反 = 信息，不是 bug）
    MR-4 order        打乱词的顺序，top-1 不变（bag-of-words 假设；char-bigram
                      分词本身不保序，违反是预期内的，度量它有多大）
    MR-5 synonym      同义词替换，不应掉出 top-3
    MR-6 stopword      增加高频停用词，top-1 不应翻转

第二组实验：给 query 加一个**归一化器**（大小写折叠 + 全半角统一 + 空白折叠），
重跑 INVARIANT 三项，量化归一化能修掉多少违反。归一化只加在查询侧，
索引不动 —— 这是刻意的最小改动。

用法：
    python3 hybrid/metamorphic_test.py            # 全跑 + 写 results/metamorphic_m3.json
    python3 hybrid/metamorphic_test.py --no-fix    # 只跑"修复前"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hybrid_rag import HybridRetriever, load_config, EVAL_SET  # noqa: E402

RESULTS = HERE.parent / "results" / "metamorphic_m3.json"

STOPWORDS = ["请问一下", "麻烦", "我想知道", "的", "一下"]


def _drop_last(q: str) -> str:
    """去掉末尾一个词：模拟 query 被截断/口语化省略，看 top-1 是否还稳。"""
    p = q.split()
    return " ".join(p[:-1]) if len(p) > 2 else q


# ---------------- 归一化器（第二组实验的自变量） ----------------
def normalize_query(q: str) -> str:
    """ASCII 大小写折叠 + NFKC（全角→半角、兼容字符合并）+ 空白折叠。
    注意：NFKC 会把中文全角标点也规范化，这是有意的（对检索无害）。"""
    t = unicodedata.normalize("NFKC", q)
    # ASCII 大小写折叠（只折 a-zA-Z，中文不受影响）
    t = "".join(c.lower() if "a" <= c <= "z" or "A" <= c <= "Z" else c for c in t)
    return " ".join(t.split())


# ---------------- 语义保持的 query 变换 ----------------
def _swapcase_ascii(q: str) -> str:
    return "".join(c.lower() if "A" <= c <= "Z" else (c.upper() if "a" <= c <= "z" else c) for c in q)


def _fullwidth_ascii(q: str) -> str:
    """ASCII 可见字符（0x21-0x7E）→ 全角（U+FF01-U+FF5E）。
    公式 chr(ord(c) - 0x21 + 0xFF01)。踩坑：第一版写成 -0x20+0xFEE0，
    落到半角片假名区（如 ',' → 'ｬ'），变换本身产生了语料里不存在的字符，
    连 NFKC 都救不回来 —— 那测的是我的变换函数，不是检索器。"""
    out = []
    for c in q:
        o = ord(c)
        out.append(chr(o - 0x21 + 0xFF01) if 0x21 <= o <= 0x7E else c)
    return "".join(out)


def _extra_space(q: str) -> str:
    return "  " + q.replace(" ", "   ") + "  \n"


def _reverse_order(q: str) -> str:
    return " ".join(reversed(q.split()))


MUTATIONS = {
    # MR-1 determinism 用 None 表示"不变换"
    "whitespace": ("MR-2", _extra_space, "INVARIANT"),
    "casewidth": ("MR-3", lambda q: _swapcase_ascii(_fullwidth_ascii(q)), "INVARIANT"),
    "order": ("MR-4", _reverse_order, "DESIRABLE"),
    "drop_last": ("MR-5", _drop_last, "DESIRABLE"),
    "stopword": ("MR-6", lambda q: "麻烦" + q + "的", "DESIRABLE"),
}


def top1(res) -> tuple:
    if not res:
        return (None, None)
    return (res[0]["doc_id"], round(float(res[0].get("score", 0.0)), 6))


def top3(res) -> list:
    return [r["doc_id"] for r in res[:3]]


def run(ret: HybridRetriever, with_fix: bool, tag: str) -> dict:
    out = {"tag": tag, "normalizer": bool(with_fix), "cases": [], "summary": {}}
    for item in EVAL_SET:
        q = item["q"]
        qs = normalize_query(q) if with_fix else q
        base = ret.retrieve(qs, k=3)
        b1, b1s = top1(base)
        # MR-1 determinism
        again = ret.retrieve(qs, k=3)
        a1, a1s = top1(again)
        out["cases"].append({
            "query": q, "mr": "MR-1", "class": "INVARIANT", "mutation": "(none)",
            "top1": b1, "score": b1s, "top1_repeat": a1, "score_repeat": a1s,
            "violation": (b1 != a1 or abs((b1s or 0) - (a1s or 0)) > 1e-9),
            "severity": "HIGH" if (b1 != a1) else "NONE",
        })
        for name, (mr, fn, cls) in MUTATIONS.items():
            try:
                mq = fn(q)
            except Exception as e:
                out["cases"].append({"query": q, "mr": mr, "class": cls,
                                     "mutation": name, "error": repr(e),
                                     "violation": False, "severity": "NONE"})
                continue
            mqs = normalize_query(mq) if with_fix else mq
            got = ret.retrieve(mqs, k=3)
            g1, _ = top1(got)
            same_top1 = (g1 == b1)
            overlap = len(set(top3(got)) & set(top3(base)))
            out["cases"].append({
                "query": q, "mr": mr, "class": cls, "mutation": name,
                "mutated_query": mq, "top1": g1, "base_top1": b1,
                "top3_base": top3(base), "top3_mut": top3(got),
                "violation": (not same_top1) if cls == "INVARIANT" else (overlap < 2),
                "severity": ("HIGH" if not same_top1 else
                             ("MED" if overlap < 2 else "NONE")),
            })
    # 汇总
    for cls in ("INVARIANT", "DESIRABLE"):
        sel = [c for c in out["cases"] if c["class"] == cls and "violation" in c]
        v = [c for c in sel if c["violation"]]
        by_mr = {}
        for c in v:
            by_mr.setdefault(c["mr"], []).append(c["query"])
        out["summary"][cls] = {
            "n": len(sel), "violations": len(v),
            "violation_rate": round(len(v) / max(1, len(sel)), 4),
            "by_mr": {k: {"n": len(val), "queries": sorted(set(val))} for k, val in by_mr.items()},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fix", action="store_true", help="只跑修复前，不跑归一化后")
    args = ap.parse_args()

    cfg, tbd = load_config()
    t0 = time.perf_counter()
    ret = HybridRetriever(cfg)
    print(f"[metamorphic] corpus={len(ret.chunks)} chunks, build={time.perf_counter()-t0:.1f}s, "
          f"normalizer={'on' if not args.no_fix else 'off'}")

    out = {"config": cfg, "tbd_defaults_used": tbd, "corpus_chunks": len(ret.chunks),
           "runs": [run(ret, with_fix=False, tag="before_normalizer")]}
    if not args.no_fix:
        out["runs"].append(run(ret, with_fix=True, tag="after_normalizer"))

    # 对比
    b = out["runs"][0]["summary"]
    a = out["runs"][1]["summary"] if len(out["runs"]) > 1 else None
    out["comparison"] = {
        cls: {
            "before": b[cls]["violations"], "before_rate": b[cls]["violation_rate"],
            "after": (a[cls]["violations"] if a else None),
            "after_rate": (a[cls]["violation_rate"] if a else None),
            "fixed_by_normalizer": (b[cls]["violations"] - a[cls]["violations"]) if a else None,
        } for cls in ("INVARIANT", "DESIRABLE")
    }

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    for cls in ("INVARIANT", "DESIRABLE"):
        s = out["runs"][0]["summary"][cls]
        c = out["comparison"][cls]
        print(f"[{cls}] 修复前违反 {s['violations']}/{s['n']} "
              f"({s['violation_rate']:.0%})  by_mr={ {k: len(v['queries']) for k, v in s['by_mr'].items()} }")
        if a:
            print(f"          归一化后违反 {c['after']}/{s['n']} ({c['after_rate']:.0%}) "
                  f"→ 修掉 {c['fixed_by_normalizer']} 例")
    print(f"[metamorphic] wrote {RESULTS}")


if __name__ == "__main__":
    main()
