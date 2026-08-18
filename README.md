# Enterprise RAG

> **Hybrid retrieval + evaluation harness for enterprise knowledge bases**

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active%20development-orange)

---

## What is this?

A production-oriented RAG (Retrieval-Augmented Generation) system designed for enterprise deployment, with built-in evaluation and hybrid retrieval strategies.

### Key Features

- **Hybrid Retrieval**: Combines keyword search (BM25) and vector search (ChromaDB) for maximum recall
- **Evaluation Harness**: Built-in retrieval accuracy + answer quality scoring — don't just build RAG, prove it works
- **Multi-tenant Architecture**: Designed for enterprise deployment with tenant isolation
- **Chunking Strategies**: Configurable chunk size, overlap, and semantic chunking options
- **Source Attribution**: Every answer links back to source documents with relevance scores
- **Cost Tracking**: Token usage and API cost monitoring per query

### Architecture

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

### Quickstart

```bash
pip install -r requirements.txt

# Index documents
python -m enterprise_rag index --source ./docs/ --chunk-size 512

# Query
python -m enterprise_rag query "What is the vacation policy?"

# Run evaluation suite
python -m enterprise_rag eval --test-set eval.jsonl
```

### Evaluation Metrics

| Metric | What It Measures |
|--------|-----------------|
| Retrieval Recall@K | Did the right chunk appear in top-K results? |
| Context Precision | How many retrieved chunks are actually relevant? |
| Answer Faithfulness | Does the answer stay grounded in retrieved context? |
| Answer Relevance | Does the answer actually address the question? |
| Cost per Query | Token usage × pricing |

---

## Status

Active development. Core retrieval pipeline + evaluation harness implemented. Multi-tenant support in progress.

## License

MIT
