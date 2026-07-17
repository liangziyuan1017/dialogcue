---
id: ADR-044
title: "Serve scored tree indexes from DB instead of app.state"
doc_kind: decision
feature_ids: [F017]
topics: [scalability, database, architecture, server]
status: accepted
created: 2026-07-17
updated: 2026-07-17
schema_version: 1
---

# Serve Scored Tree Indexes from DB Instead of app.state

## What

Stop holding the scored tree + node index + label-set index in `app.state` for the process lifetime. Serve node/label lookups from DB queries via asyncpg (ADR-027 runtime driver). The server boot no longer materializes the full scored tree into memory.

## Why

At 100k dialogs, `app.state` tree + indexes consume ~200 MB resident for the entire server lifetime. This is wasted memory — the data is already in PostgreSQL with pgvector HNSW indexes. Serving from DB queries bounds server memory to O(query_result) instead of O(corpus).

asyncpg (ADR-027) is already the runtime driver with binary protocol — query latency for single node lookups is sub-millisecond. The scored tree is queryable by `path_signature` and `script_id` with existing indexes.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep app.state tree + indexes | ~200 MB resident at 100k; wasted memory; duplicates DB data |
| LRU cache on top of DB queries | Premature optimization; measure first, add cache only if latency warrants |
| Materialize tree on-demand per request | Worse than app.state — rebuilds tree on every request |
| Read tree from JSONL file on each request | No indexes; slower than DB; still materializes full tree |

## Impact

- `server.py` startup no longer loads full tree into `app.state`
- Node lookup, label lookup, label-set index → DB queries via `AsyncSentenceDB`
- `retrieval_engine.py` queries DB instead of reading from `app.state`
- **Risk**: query latency for real-time recommendation — needs performance verification in TDD phase
- ADR-027 compatible (asyncpg already wired into server)
