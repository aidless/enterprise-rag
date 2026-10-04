# Enterprise RAG

> **Hybrid retrieval + evaluation harness for enterprise knowledge bases** — 设计文档（spec-only），暂无代码

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-design%20spec--only-lightgrey)

---

## ⚠️ 现状（2026-10-03）

**本仓库目前只有这份 README——没有任何代码。** 下面的架构图、接口与指标是设计目标，不是已实现功能。

- 相关实现进度见姊妹仓 [`enterprise-rag-saas`](https://github.com/aidless/enterprise-rag-saas)（同样处于未完成状态，见其 README）。
- 如果你在找**现在就能跑**的 RAG 方案，请使用成熟开源：LlamaIndex、LangChain Retrieval、txtai 等。

## 设计目标

A production-oriented RAG (Retrieval-Augmented Generation) system designed for enterprise deployment, with built-in evaluation and hybrid retrieval strategies.

### Key Features（规划）

- **Hybrid Retrieval**: Combines keyword search (BM25) and vector search (ChromaDB) for maximum recall
- **Evaluation Harness**: Built-in retrieval accuracy + answer quality scoring — don't just build RAG, prove it works
- **Multi-tenant Architecture**: Designed for enterprise deployment with tenant isolation
- **Chunking Strategies**: Configurable chunk size, overlap, and semantic chunking options
- **Source Attribution**: Every answer links back to source documents with relevance scores
- **Cost Tracking**: Token usage and API cost monitoring per query

### 目标架构

```
┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│   Query      │───→│  Hybrid       │───→│  LLM         │───→ Answer + Sources
│   (user)     │    │  Retriever    │    │  Generator   │
└──────────────┘    │  (BM25+vector)│    └──────────────┘
                    └───────┬───────┘
                            │
                    ┌───────┴───────┐
                    │  ChromaDB     │
                    │  (vectors)    │
                    └───────────────┘
```

### 目标接口（尚未实现）

```bash
# Index documents
python -m enterprise_rag index --source ./docs/ --chunk-size 512

# Query
python -m enterprise_rag query "What is the vacation policy?"

# Run evaluation suite
python -m enterprise_rag eval --test-set eval.jsonl
```

### 评估指标（设计）

| Metric | What It Measures |
|--------|-----------------|
| Retrieval Recall@K | Did the right chunk appear in top-K results? |
| Context Precision | How many retrieved chunks are actually relevant? |
| Answer Faithfulness | Does the answer stay grounded in retrieved context? |
| Answer Relevance | Does the answer actually address the question? |
| Cost per Query | Token usage × pricing |

---

## Status

**Design / spec only.** 仓库当前不含实现代码；实现推进时更新本节。诚实状态优于虚假徽章。

## License

MIT
