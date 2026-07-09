---
id: ADR-028
title: "SQL-side cosine scoring: move vec_score computation from Python to PostgreSQL"
doc_kind: decision
feature_ids: [F006, F007b]
topics: [vector-search, pgvector, hnsw, retrieval, performance]
status: accepted
created: 2026-07-01
updated: 2026-07-01
schema_version: 2
---

# SQL-Side Cosine Scoring

## What

Move cosine similarity computation (`vec_score`) from Python/numpy to PostgreSQL via pgvector's `<=>` operator. Add `SentenceDB.search_by_nodes()` that returns sentences with `vec_score` pre-computed in SQL, eliminating the need to transfer raw embedding vectors to Python.

## Why

The previous flow required two DB round trips plus a vector transfer:

1. `db.get_sentences_by_node()` × N nodes → fetch sentence metadata (no embeddings)
2. `db.get_vectors(script_ids)` → fetch all 1024-dim float arrays to Python
3. `numpy.dot()` / `numpy.linalg.norm()` → compute cosine similarity in Python

For a candidate pool of K sentences, step 2 transfers K × 1024 × 4 bytes = ~4KB per sentence from DB to Python. Step 3 re-computes what pgvector already supports natively in C.

The new flow:

1. `db.search_by_nodes(query_vec, node_ids)` → single query, returns sentences with `vec_score` computed in SQL
2. Python uses pre-computed `vec_score` directly in weighted fusion ranking

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep Python cosine | Transfers 4KB per candidate; redundant computation; HNSW index unused |
| Pure SQL ranking (all signals in SQL) | `bg_boost` requires JSONB dict comparison not expressible in SQL; bitmask is a soft score (partial match), not a hard filter |
| HNSW ANN search (no node filter) | Must filter by `node_id = ANY(...)` to scope to matching nodes; HNSW alone would search all nodes |

## Impact

- **`db.py`**: New `search_by_nodes()` method. `get_vectors()` retained for backward compat but no longer called in serving path.
- **`retrieval_engine.py`**: `recommend()` uses `search_by_nodes()` when both `db` and `query_vec` are available; falls back to per-node fetch when DB available but no query vector.
- **`retrieval_ranking.py`**: `rank_sentences()` checks for pre-computed `vec_score` on pool entries; skips Python cosine if present. `compute_vec_similarity()` retained as fallback.
- **Bitmask**: Remains a **soft score** in Python-side ranking (not a SQL WHERE filter), preserving partial-match semantics.
- **HNSW index**: Now actually used by the query planner for the `ORDER BY embedding <=> query_vec` clause within the `node_id` filter scope.
- **Table schema**: No changes. The HNSW index already exists.
