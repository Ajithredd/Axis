---
name: advanced-rag-pipeline
description: Best practices for data ingestion, chunking, retrieval, reranking, and evaluation in advanced Retrieval-Augmented Generation.
---

# Advanced RAG Pipelines

Guidelines for implementing and optimizing production-grade Retrieval-Augmented Generation.

## 1. Pipeline Phases

### A. Ingestion & Preprocessing
- **Semantic Chunking:** Break documents based on semantic content shifts rather than fixed character limits.
- **Metadata Tagging:** Enrich every chunk with source IDs, titles, section headings, and creation dates.

### B. Retrieval & Search
- **Hybrid Search:** Query both dense vector indices (semantic search) and sparse indices (e.g., BM25/keyword search).
- **Query Rewriting:** Use step-back prompting or HyDE (Hypothetical Document Embeddings) to expand user queries before searching.
- **Reranking:** Always run retrieved chunks through a Cross-Encoder Reranker model to fix the "lost in the middle" relevance decay.

### C. Evaluation
- **Faithfulness & Relevance:** Assess responses using automated RAGAS metrics or LLM-as-a-judge patterns.

---

## 2. Implementation Checklist

- [ ] Use hybrid dense-sparse vector retrievers.
- [ ] Configure metadata filters to narrow down the search space prior to execution.
- [ ] Implement query expansion to handle conversational or ambiguous search terms.
- [ ] Log retrieval metrics (Recall, Precision) and generation metrics to a monitoring system.
