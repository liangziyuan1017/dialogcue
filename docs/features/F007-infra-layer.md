---
id: F007
name: Infrastructure Layer
status: review
owner: agent
source: F007-F009-implementation-steps.md
created: 2026-06-24
updated: 2026-06-25
review_submitted: 2026-06-25
depends_on: [F005, F006]
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F007: Infrastructure Layer

## Why

The original system used in-memory JSON files and char-ngram TF-IDF for retrieval. The spec (see `SCBGE_GUIDELINE.md`, [F009 API contract](F009-api-server.md)) requires PostgreSQL + pgvector for hybrid vector + bitmask + FTS search, and a REST + Socket.IO API for integration with the call platform. F007 provides the shared infrastructure that F007b, F008, and F009 build on.

## What

### PostgreSQL + pgvector Database Client

`db.py` module with `SentenceDB` class:

- **Schema**: `nodes` table (tree structure), `sentences` table (script text + embedding + metadata), `taxonomy_keywords` table (keyword → node mapping for FTS)
- **pgvector**: `sentences.embedding vector(1024)` column for cosine similarity search
- **Operations**: `create_tables()`, `upsert_nodes()`, `upsert_sentences()`, `search_similar()` (vector search), `keyword_search()` (FTS), `taxonomy_keyword_search()`, `get_vectors()`, `get_node_by_signature()`, `get_sentences_by_node()`

### Embedding Client

`f007_infrastructure/embeddings.py`:

- **Model**: bge-m3 (1024-dim) served via Ollama on `localhost:11434`
- **API**: OpenAI-compatible (`/v1/embeddings`)
- **Functions**: `embed_single(text)`, `embed_texts(texts)` (batch)
- **Config**: `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIM` env vars

### LLM Client

`f007_infrastructure/llm_client.py`: DeepSeek chat model client (`call_deepseek()`, `call_deepseek_json()`)

### Retry Utility

`f007_infrastructure/retry.py`: `retry_call()` with exponential backoff

## Passing Criteria

- `SentenceDB` creates all 3 tables with correct schema
- `upsert_nodes()` and `upsert_sentences()` write and update records
- `search_similar()` returns cosine-similar sentences via pgvector
- `keyword_search()` and `taxonomy_keyword_search()` return FTS matches
- `embed_single()` returns 1024-dim float list
- `embed_texts()` returns list of 1024-dim float lists
- `retry_call()` retries on exception with backoff

## Dependencies

- F005 (Context Tagging & Quality Scoring) — scored tree data to populate PostgreSQL
- F006 (Retrieval & Ranking Engine) — retrieval functions that consume PostgreSQL data

## Links

- [F007-F009-implementation-steps.md](F007-F009-implementation-steps.md) — Steps 1-3
- [ADR-024](../decisions/ADR-024-embedding-architecture.md) — Embedding architecture decision
- [F007-F009 review request](F007-F009-review-request.md) — Combined review

## Implementation Plan

See [implementation-plan.md](F007-implementation-plan.md)

## Design Decisions

- **Ollama for local embeddings**: No external API dependency, no per-call cost, offline-capable. See ADR-024.
- **OpenAI-compatible API**: Ollama exposes `/v1/embeddings` — reuse `openai` Python client, no custom HTTP code.
- **Python-side ranking**: Fetch candidates from PostgreSQL, compute `final_score` in Python. `bg_boost` requires JSONB dict comparison not expressible in SQL. Tradeoff: ~1ms extra latency for flexibility.
- **pgvector for vector search**: Native PostgreSQL extension, no separate vector DB. Hybrid: vector + bitmask + FTS in one query.
- **Optional embedding in score_tree.py**: `embed_fn` param — when `db=None`, embeddings are skipped (backward compat for offline scoring without PG).

## Files

| File | Purpose |
|------|---------|
| `src/f007_infrastructure/db.py` | PostgreSQL + pgvector database client (SentenceDB) |
| `src/f007_infrastructure/embeddings.py` | Embedding client (bge-m3 via Ollama) |
| `src/f007_infrastructure/llm_client.py` | DeepSeek LLM client |
| `src/f007_infrastructure/retry.py` | Retry utility with exponential backoff |
| `src/tests/f007_infrastructure/test_db.py` | Unit tests for SentenceDB |
| `src/tests/f007_infrastructure/test_db_integration.py` | Integration tests (require PostgreSQL) |
| `src/tests/f007_infrastructure/test_embeddings.py` | Unit tests for embedding client |

## Scaling Path

Migration path from 108 → 100,000+ nodes. Retrieval is O(1) hash lookup regardless of tree size; scaling challenges are storage, build-time, and index maintenance — not retrieval latency.

| Dimension | Current (108 records) | Target (50K+ records) | Solution |
|-----------|---------------------|----------------------|----------|
| Nodes | 309 | 100,000+ | Tree grows with record diversity, not linearly with records |
| Node storage | JSON file | PG `nodes` table with `path_signature` B-tree index | O(log N) lookup |
| Sentence storage | JSON in-memory pools | PG `sentences` table with `node_id` index | Filter + rank in SQL |
| Vector search | char-ngram TF-IDF | pgvector HNSW index | O(log N) approximate KNN |
| Full-text search | None | PG tsvector + GIN index | BM25-ish keyword search |
| Build time | ~30s (with LLM merge) | Batch LLM + incremental rebuild | Only rebuild affected subtrees on new data |
| Child lookup | Linear scan of `children[]` | Hash map `branch_key → child` per node | O(1) child resolution |
| Context filter | Python loop | PG bitwise op: `bg_bitmask_int & ? = bg_bitmask_int` | Index + SQL filter |
| Retrieval | JSON load + tree walk | Hash lookup + PG SELECT + pgvector | O(1) + O(pool_size) |

Migration steps: (1) JSON → PostgreSQL with `path_signature` column; (2) hash index for child lookup; (3) incremental rebuild of affected subtrees; (4) batch LLM merge with merge cache; (5) pgvector HNSW tuning (`ef_construction`, `m`).

Managed hosting: Supabase (PostgreSQL + pgvector + realtime), Neon (serverless Postgres with branching), or self-hosted `docker run postgres:16-pgvector`.
