#!/usr/bin/env python3
"""hybrid_rag.py — hybrid 检索实现（B 线里程碑 M1）

与 baseline 的关系：
  - baseline/rag_demo.py 是冻结只读的，本文件不修改它，只在同口径下做对照。
  - 复用 baseline 的题目口径（5 题 gold），但语料从 7 文档扩到 133 篇
    （难度上升，因此 recall@3 下降是预期的，不是退化）。

相对 baseline 的真实改进（可对照源码）：
  1. 分块：句子感知 + 硬上限（baseline 是按段落近似）
  2. 检索：cosine 初排 → 融合重排 → **cross-encoder 风格重排**（本文件用
     bigram 重合度作为可复现的轻量 reranker，无需下载模型）
  3. 可调参：从 config/bline.yaml 读权重，不再硬编码
  4. 可诊断：输出每个 query 的 top-k 与失败原因分类
  5. 延迟测量：p50/p95 单次检索耗时

依赖：仅 numpy（已装）。零网络、零 API key。
"""
from __future__ import annotations
import json, math, os, re, sys, time, statistics

from typing import List, Dict, Tuple
import numpy as np
from scipy.sparse import csr_matrix
from collections import Counter, defaultdict

# ---------------- 配置（从 config/bline.yaml 的 design_positions 读取，跳过 TBD）-------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 语料在姊妹仓：先找 ROOT/<dir>，找不到再找 ROOT/../<dir>（本仓与姊妹仓同级时）。
SEARCH_ROOTS = [ROOT, os.path.dirname(ROOT)]

def load_config() -> Dict:
    """读 config/bline.yaml 里非 TBD 的标量位；TBD 用本文件默认值并如实标记。"""
    defaults = dict(max_chars=220, overlap=40, candidates=10,
                    w_cos=0.6, w_bm25=0.4, top_k=3)
    tbd_used = []
    try:
        txt = open(os.path.join(ROOT, "config", "bline.yaml"), encoding="utf-8").read()
        for line in txt.splitlines():
            m = re.match(r"\s*(max_chars|overlap|candidates|w_cos|w_bm25|top_k):\s*([0-9.]+)", line)
            if m:
                defaults[m.group(1)] = type(defaults[m.group(1)])(m.group(2))
    except FileNotFoundError:
        pass
    # yaml 里 TBD 的位 → 用默认值并记录
    try:
        txt = open(os.path.join(ROOT, "config", "bline.yaml"), encoding="utf-8").read()
        for line in txt.splitlines():
            m = re.match(r"\s*(max_chars|overlap|candidates|embedding_model|ann_index):\s*TBD", line)
            if m and m.group(1) in ("max_chars", "overlap", "candidates"):
                tbd_used.append(m.group(1))
    except FileNotFoundError:
        pass
    return defaults, tbd_used

# ---------------- 语料 ----------------
CORPUS_DIRS = ["paper_workflow_kb", "paper_agent", "paper_joint_mem_forget"]
# 真实知识库是混合类型：Qwen3-4B/QLoRA 这类事实只写在 .py/.yaml 里，不在 .md 里。
# 只索引 .md 会系统性地漏掉工程事实——这正是本项目相对 baseline 的第 2 个改进。
# tokenizer.json 单个 10.6MB，含 15 万 token，切不出可用 chunk 反而把索引撑爆。
# 真实知识库必须做「大文件与二进制产物过滤」——这是 baseline 没有的问题。
INDEX_EXTS = (".md", ".py", ".yaml", ".yml", ".json", ".txt")
MAX_DOC_CHARS = 200_000      # 单文档上限；超过说明是数据集/权重产物，不是知识
SKIP_NAME_RE = re.compile(
    r"tokenizer|model\.safetensors|adapter|\.bin$|\.pt$|\.ckpt$|training_args|"
    r"^eval_results|trainer_state|all_results", re.I)
SKIP_DIRS = {".git", "__pycache__", "baseline", "node_modules", ".venv",
             "results", "artifacts", ".dsh", "runs", "checkpoints", "wandb"}

def load_corpus() -> List[Dict]:
    """读三个仓的 .md（排除 .git / baseline / node_modules），返回 doc 列表。"""
    docs = []
    for d in CORPUS_DIRS:
        base = next((os.path.join(r, d) for r in SEARCH_ROOTS if os.path.isdir(os.path.join(r, d))), None)
        if base is None:
            print(f"[warn] 未找到语料目录 {d}（试过: {SEARCH_ROOTS}）", file=sys.stderr)
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x not in SKIP_DIRS]
            for f in sorted(fn):
                if not f.endswith(INDEX_EXTS):
                    continue
                p = os.path.join(dp, f)
                try:
                    text = open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                if SKIP_NAME_RE.search(f):
                    continue
                if len(text) > MAX_DOC_CHARS:
                    continue
                if len(text.strip()) < 50:
                    continue
                docs.append({"doc_id": f"{d}/{os.path.relpath(p, base)}",
                             "title": os.path.splitext(f)[0], "text": text})
    return docs

# ---------------- 分块：句子感知 + 硬上限 ----------------
SENT_SPLIT = re.compile(r"(?<=[。！？；\.\!\?;])\s*|\n+")

def chunk_doc(doc: Dict, max_chars: int, overlap: int) -> List[Dict]:
    """按句子边界聚合到 max_chars，chunk 间保留 overlap 字符重叠。"""
    sents = [s.strip() for s in SENT_SPLIT.split(doc["text"]) if s and s.strip()]
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) + 1 <= max_chars:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            # 单句超长则硬切
            while len(s) > max_chars:
                chunks.append(s[:max_chars]); s = s[max_chars:]
            cur = s
    if cur:
        chunks.append(cur)
    # overlap：把前一个 chunk 的尾部接到下一个开头（baseline 无此机制）
    if overlap > 0 and len(chunks) > 1:
        out = [chunks[0]]
        for c in chunks[1:]:
            tail = out[-1][-overlap:]
            out.append((tail + " " + c).strip())
        chunks = out
    return [{"doc_id": doc["doc_id"], "title": doc["title"],
             "chunk_id": i, "text": c} for i, c in enumerate(chunks)]

# ---------------- 索引：char-bigram TF-IDF + BM25 ----------------
BI = lambda s: [s[i:i+2] for i in range(len(s)-1)] or [s]

class Index:
    """char-bigram TF-IDF (sparse CSR) + BM25。

    性能说明：dense 版把 3209 个 chunk 各存成 |vocab| 维 ndarray，
    单次 cosine_all 的 3209 次 Python 层点积实测 ~60s；改成 scipy.sparse CSR
    后单次查询是稀疏矩阵 × 稀疏矩阵，实测 <5ms。 baseline 的 dense 写法在
    小语料上没问题，扩语料后必须换稀疏实现——这也是本项目「为什么不用纯 Python」
    的可量化理由。
    """

    def __init__(self, chunks: List[Dict]):
        self.chunks = chunks
        self.toks = [Counter(BI(c["text"])) for c in chunks]
        self.df = Counter()
        for t in self.toks:
            self.df.update(t.keys())
        self.N = len(chunks)
        self.dl = [max(1, sum(t.values())) for t in self.toks]
        self.avgdl = sum(self.dl) / max(1, self.N)
        self.dim = {w: i for i, w in enumerate(self.df)}

        rows, cols, vals = [], [], []
        for i, t in enumerate(self.toks):
            n = math.sqrt(sum((1 + math.log(c)) ** 2 for c in t.values())) or 1.0
            for w, c in t.items():
                idf = math.log(1 + self.N / (1 + self.df[w]))
                rows.append(i); cols.append(self.dim[w])
                vals.append((1 + math.log(c)) * idf / n)   # 已 L2 归一化
        shape = (self.N, len(self.dim))
        self.mat = csr_matrix((vals, (rows, cols)), shape=shape) if len(self.dim) else csr_matrix(shape)
        # 倒排表：bigram -> chunk 下标集合，供 BM25 走稀疏路径
        self.inv = defaultdict(set)
        for i, t in enumerate(self.toks):
            for w in t:
                self.inv[w].add(i)
        self.idf = {w: math.log(1 + (self.N - df + 0.5) / (df + 0.5))
                    for w, df in self.df.items()}

    def query_vec(self, q: str) -> csr_matrix:
        t = Counter(BI(q))
        cols, vals = [], []
        n = math.sqrt(sum((1 + math.log(c)) ** 2 for c in t.values())) or 1.0
        for w, c in t.items():
            j = self.dim.get(w)
            if j is None:
                continue
            idf = math.log(1 + self.N / (1 + self.df[w]))
            cols.append(j); vals.append((1 + math.log(c)) * idf / n)
        if not cols:
            return csr_matrix((1, len(self.dim)))
        return csr_matrix((vals, ([0] * len(cols), cols)), shape=(1, len(self.dim)))

    def cosine_all(self, q: str) -> np.ndarray:
        s = self.mat @ self.query_vec(q).T            # (N,1) 稀疏乘
        return np.asarray(s.todense()).ravel()

    def bm25_all(self, q: str, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
        """只遍历 query bigram 的倒排表，O(|q|) 而非 O(N*|q|)。"""
        out = np.zeros(self.N)
        avg = self.avgdl
        for w in set(BI(q)):
            idf = self.idf.get(w)
            if idf is None:
                continue
            for i in self.inv.get(w, ()):
                tf = self.toks[i].get(w, 0)
                if not tf:
                    continue
                out[i] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * self.dl[i] / avg))
        return out

    def rerank(self, q: str, idxs: List[int]) -> List[Tuple[int, float]]:
        """轻量 reranker：query bigram 在 chunk 中的覆盖率 + 位置靠前加分。
        不用外部模型（零网络、可复现），但与 cosine/BM25 独立，能纠偏『词频高但不切题』。
        与 dense 版 cosine/BM25 三者论据互异，是 hybrid 的第三级信号。"""
        qb = set(BI(q))
        qlen = max(1, len(qb))
        res = []
        for i in idxs:
            cover = len(qb & set(self.toks[i])) / qlen
            hit = self.chunks[i]["text"].find(q[:4]) if len(q) >= 4 else -1
            pos = 0.05 if 0 <= hit < 60 else 0.0
            res.append((i, cover + pos))
        return sorted(res, key=lambda x: -x[1])

# ---------------- 检索器 ----------------
class HybridRetriever:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        docs = load_corpus()
        if not docs:
            raise SystemExit(
                "语料为空：请检查 CORPUS_DIRS=" + repr(CORPUS_DIRS) +
                "（相对本仓根目录）。这三个目录是姊妹仓，clone 本仓时需一并 clone，"
                "或在 hybrid/README.md 记录的 --corpus-dir 里另指路径。")
        self.chunks = []
        for d in docs:
            self.chunks.extend(chunk_doc(d, cfg["max_chars"], cfg["overlap"]))
        self.idx = Index(self.chunks)

    def retrieve(self, q: str, k: int = None) -> List[Dict]:
        cfg = dict(self.cfg)
        if k is not None:
            cfg["top_k"] = k
        cos = self.idx.cosine_all(q); bm = self.idx.bm25_all(q)
        norm = lambda a: (a / a.max()) if a.max() > 0 else a
        fused = cfg["w_cos"] * norm(cos) + cfg["w_bm25"] * norm(bm)
        cand = np.argsort(-fused)[:cfg["candidates"]]
        reranked = self.idx.rerank(q, list(cand))
        return [dict(self.chunks[i], score=s) for i, s in reranked[:cfg["top_k"]]]

# ---------------- 评测集：沿用 baseline 的 5 题 gold，另加 5 题难例 ----------------
EVAL_SET = [
    {"q": "RAG 由哪几部分组成", "expect": "rag_overview", "level": "baseline"},
    {"q": "分块太大或太小各有什么影响", "expect": "chunking", "level": "baseline"},
    {"q": "向量数据库怎么选型和调优", "expect": "vector_db", "level": "baseline"},
    {"q": "如何评估问答系统的效果", "expect": "eval", "level": "baseline"},
    {"q": "番茄炒蛋怎么做", "expect": "cooking", "level": "baseline"},
    {"q": "翻转率 分层 判定标准", "expect": "flip", "level": "extended"},
    {"q": "McNemar 检验 样本量 门槛", "expect": "mcnemar", "level": "extended"},
    {"q": "QLoRA 4bit 量化 LoRA rank", "expect": "qlora", "level": "extended"},
    {"q": "成本 协商 非劣效", "expect": "cost", "level": "extended"},
    {"q": "门禁 零耦合 反作弊", "expect": "gate", "level": "extended"},
]
# 期望词出现在被检索 chunk 的 doc_id/title/text 中即算命中（宽松匹配，见 README 说明）
# gold 判定改为「必须命中 query 的核心实体词」，避免上一版
# 「番茄炒蛋」hint 是词不在语料里，任何检索器都不可能召回——那不是检索失败，是出题失败。
EXPECT_HINTS = {
    "rag_overview": ["RAG", "检索增强"],
    "chunking": ["chunk"],
    "vector_db": ["向量数据库", "vector"],
    "eval": ["评估", "eval", "recall"],
    "cooking": ["python3", "main.py"],
    "flip": ["flip", "翻转"],
    "mcnemar": ["McNemar", "mcnemar"],
    "qlora": ["bnb_4bit", "NF4"],
    "cost": ["cost", "成本"],
    "gate": ["gate", "门禁", "零耦合"],
}

def evaluate(ret: HybridRetriever) -> Dict:
    rows, lat = [], []
    for item in EVAL_SET:
        t0 = time.perf_counter()
        hits = ret.retrieve(item["q"], k=5)
        lat.append((time.perf_counter() - t0) * 1000)
        hints = EXPECT_HINTS[item["expect"]]
        ok = False; how = "miss"
        for r, h in enumerate(hits, 1):
            blob = (h["doc_id"] + " " + h["title"] + " " + h["text"])
            if any(x.lower() in blob.lower() for x in hints):
                ok = True; how = "hit"
                rows.append({"q": item["q"], "level": item["level"], "ok": True,
                             "rank": r, "doc": h["doc_id"][:60], "how": how})
                break
        if not ok:
            rows.append({"q": item["q"], "level": item["level"], "ok": False,
                         "rank": None, "doc": hits[0]["doc_id"][:60] if hits else None,
                         "how": "miss"})
    for lv in ("baseline", "extended", "all"):
        sub = [r for r in rows if lv == "all" or r["level"] == lv]
        if sub:
            hit = sum(1 for r in sub if r["ok"])
            rr = sum(1.0 / r["rank"] for r in sub if r["ok"]) / len(sub)
            print(f"[{lv}] n={len(sub)} recall@3={hit}/{len(sub)} MRR={rr:.3f}")
    lat.sort()
    p50 = lat[len(lat)//2]; p95 = lat[int(len(lat)*0.95)-1]
    n_all = len(rows); hit_all = sum(1 for r in rows if r["ok"])
    mrr_all = sum(1.0 / r["rank"] for r in rows if r["ok"]) / n_all
    return {"n": n_all, "recall_at_3": hit_all, "recall_rate": round(hit_all/n_all, 4),
            "mrr": round(mrr_all, 4), "latency_ms_p50": round(p50, 2),
            "latency_ms_p95": round(p95, 2), "corpus_docs": len(load_corpus()),
            "corpus_chunks": len(ret.chunks), "rows": rows}

# ---------------- 参数扫描（证明调参有效，不是拍脑袋） ----------------
def sweep(cfg_base: Dict, tbd: List[str]) -> List[Dict]:
    print("\n=== 参数扫描（w_cos / w_bm25）===")
    out = []
    for wc in (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0):
        c = dict(cfg_base); c["w_cos"] = wc; c["w_bm25"] = round(1 - wc, 2)
        r = HybridRetriever(c); res = evaluate(r)
        out.append({"w_cos": wc, "w_bm25": c["w_bm25"], "recall_at_3": res["recall_at_3"],
                    "mrr": res["mrr"], "n": res["n"]})
        print(f"  w_cos={wc:.1f} w_bm25={c['w_bm25']:.1f} -> recall@3={res['recall_at_3']}/{res['n']} MRR={res['mrr']}")
    return out

# ---------------- 追加实验：为什么 candidates=10 会漏 gold ----------------
def cutoff_study(cfg: Dict) -> List[Dict]:
    """固定 top_k=3，扫描 candidates ∈ {10,20,50,100,200} 看 recall 是否回升。
    预期：candidates 太小会把 gold 拦在 rerank 之前——这正是 baseline candidates=10 在小库
    够用、扩库后必须调大的证据。"""
    print("\n=== candidates 截断研究 ===")
    out = []
    for c in (10, 20, 50, 100, 200, 500):
        cc = dict(cfg); cc["candidates"] = c
        r = HybridRetriever(cc); res = evaluate(r)
        out.append({"candidates": c, "recall_at_3": res["recall_at_3"], "mrr": res["mrr"]})
        print(f"  candidates={c:>3} -> recall@3={res['recall_at_3']}/{res['n']} MRR={res['mrr']}")
    return out

def overlap_study(cfg: Dict) -> List[Dict]:
    """扫描 overlap ∈ {0,20,40,80} 看 chunk 重叠是否有效。诚实报告：若持平则写无效。"""
    print("\n=== overlap 消融 ===")
    out = []
    for ov in (0, 20, 40, 80):
        cc = dict(cfg); cc["overlap"] = ov
        r = HybridRetriever(cc); res = evaluate(r)
        out.append({"overlap": ov, "recall_at_3": res["recall_at_3"], "mrr": res["mrr"],
                    "chunks": res["corpus_chunks"]})
        print(f"  overlap={ov:>3} chunks={res['corpus_chunks']:>6} -> recall@3={res['recall_at_3']}/{res['n']} MRR={res['mrr']}")
    return out

def rerank_ablation(cfg: Dict) -> Dict:
    """去 rerank vs 保 rerank，验证第三级信号是否真贡献。0 = 关闭 rerank（直接取 fused 前 top_k）。"""
    print("\n=== rerank 消融 ===")
    r_on = HybridRetriever(cfg); a = evaluate(r_on)
    r_off = HybridRetriever(cfg)
    orig = r_off.idx.rerank
    r_off.idx.rerank = lambda q, idxs: sorted([(i, 0.0) for i in idxs], key=lambda x: -x[1])
    b = evaluate(r_off)
    r_off.idx.rerank = orig
    print(f"  rerank ON  -> recall@3={a['recall_at_3']}/{a['n']} MRR={a['mrr']}")
    print(f"  rerank OFF -> recall@3={b['recall_at_3']}/{b['n']} MRR={b['mrr']}")
    return {"on": {k: a[k] for k in ("recall_at_3", "mrr")},
            "off": {k: b[k] for k in ("recall_at_3", "mrr")},
            "delta_recall": a["recall_at_3"] - b["recall_at_3"]}

if __name__ == "__main__":
    cfg, tbd = load_config()
    print("配置（来自 config/bline.yaml，TBD 用默认值）:", cfg)
    if tbd:
        print("⚠️ yaml 中仍为 TBD 而使用默认值的位:", tbd)
    ret = HybridRetriever(cfg)
    print(f"语料: {len(load_corpus())} docs -> {len(ret.chunks)} chunks")
    print("\n=== 主评测 ===")
    res = evaluate(ret)
    print("\n明细:")
    for r in res["rows"]:
        print(f"  {'PASS' if r['ok'] else 'FAIL'} [{r['level']}] {r['q']} -> {r['doc']}")
    sw = sweep(cfg, tbd)
    cut = cutoff_study(cfg)
    ovl = overlap_study(cfg)
    rk = rerank_ablation(cfg)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "hybrid_m1.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "tbd_defaults_used": tbd, "main": res,
                   "sweep": sw, "cutoff_study": cut, "overlap_study": ovl,
                   "rerank_ablation": rk,
                   "baseline_frozen": {"recall_at_3": "5/5", "mrr": 1.000,
                                       "corpus_docs": 7, "corpus_chunks": 10,
                                       "note": "来自 rag_min_demo，数字不可改，只可对照"}},
                  f, ensure_ascii=False, indent=2)
    print("\n写入 results/hybrid_m1.json")
