# F007: Infrastructure Layer — Implementation Plan

**Feature:** F007 — `docs/features/F007-infra-layer.md`
**Goal:** Provide shared infrastructure (PostgreSQL + pgvector, embedding client, LLM client, retry utility) that F007b, F008, and F009 build on.
**Acceptance Criteria:** See F007 feature doc
**Architecture:** PostgreSQL with pgvector extension for hybrid vector + bitmask + FTS search. Ollama for local bge-m3 embeddings. DeepSeek API for LLM calls.
**Tech Stack:** Python, psycopg2, pgvector, openai (Ollama-compatible), asyncio

---

### Task 1: PostgreSQL + pgvector Database Client

**Files:**
- Create: `src/f007_infrastructure/db.py`
- Test: `src/tests/infra/test_db.py`

**Step 1:** Write failing test for `SentenceDB` — `create_tables()`, `upsert_nodes()`, `upsert_sentences()`, `search_similar()`, `keyword_search()`, `get_sentences_by_node()`, `get_node_by_signature()`.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement `SentenceDB` with psycopg2 + pgvector. Schema: `nodes` (id, state_id, path_signature, branch_key, parent_id, depth), `sentences` (id, script_id, node_id, script_text, bg_bitmask_int, win_rate, sas, embedding, script_tsv), `taxonomy_keywords` (group_name, keyword, tsv). Indexes: HNSW on embedding, GIN on tsv, B-tree on path_signature.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 2: Embedding Client

**Files:**
- Create: `src/f007_infrastructure/embeddings.py`
- Test: `src/tests/infra/test_embeddings.py`

**Step 1:** Write failing test for `embed_single()` returning 1024-dim list, `embed_texts()` returning list of 1024-dim lists.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement using `openai` Python client pointed at Ollama `/v1/embeddings` endpoint. Config via `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_DIM` env vars.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 3: LLM Client + Retry Utility

**Files:**
- Modify: `src/f007_infrastructure/llm_client.py` (already exists)
- Modify: `src/f007_infrastructure/retry.py` (already exists)
- Test: `src/tests/infra/test_llm_client.py`, `src/tests/infra/test_deps.py`

**Step 1:** Verify existing `llm_client.py` and `retry.py` meet F007 passing criteria. Add any missing tests.

**Step 2:** Run tests to verify.

**Step 3:** Commit.

---

### Task 4: Integration Tests

**Files:**
- Test: `src/tests/infra/test_db_integration.py`

**Step 1:** Write integration test that creates tables, upserts data, runs vector search and FTS, verifies results. Requires running PostgreSQL + pgvector.

**Step 2:** Run integration test.

**Step 3:** Commit.
