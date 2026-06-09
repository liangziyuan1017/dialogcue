---
id: ADR-002
title: "Adopt hybrid search (lexical + semantic) for memory retrieval"
doc_kind: decision
feature_ids: [F102]
topics: [memory, retrieval, search]
status: accepted
created: 2026-02-10
updated: 2026-03-01
schema_version: 1
supersedes: []
---

# ADR-002: Hybrid Search for Memory Retrieval

## What

Implement a hybrid retrieval model combining BM25 lexical search and vector similarity
search, fused via Reciprocal Rank Fusion (RRF).

## Why

Pure lexical search misses conceptual similarity. Pure semantic search has poor exact-ID
lookup precision. Hybrid with RRF provides the best of both: top-1 precision for exact
lookups (lexical) and high top-3 recall for concept queries (semantic).

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Lexical only | Poor concept recall; can't find "port allocation" when query is "network setup" |
| Semantic only | Exact ID lookup precision drops; "ADR-008" may not rank #1 |
| BM25 + learning-to-rank | Requires training data we don't have yet |
