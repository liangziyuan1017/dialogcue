# F011: Vector Retrieval Integration — Implementation Plan

**Feature:** F011 — `docs/features/F011-vector-retrieval-integration.md`
**Goal:** Wire F010 infra into F005 (embedding + PG load) and F006 (vector sim + unified ranking).
**Acceptance Criteria:**
- `decision_tree_scored.json` has `context_vec_id` on each sentence
- PostgreSQL `nodes` and `sentences` populated after scoring
- `compute_vec_similarity()` returns cosine similarity from PostgreSQL
- `rank_sentences()` uses unified fusion: 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost
- No `compute_context_similarity` or `_rank_limited` remains
- `recommend()` returns `vec_score`, `final_score`, `conversation_state`
- Candidates from PostgreSQL, not in-memory JSON
**Architecture:** In score_tree.py, after scoring, call embed_texts() for all sentences, then upsert to PostgreSQL. In retrieval_ranking.py, replace TF-IDF context sim with vector cosine sim from PostgreSQL, merge dual strategy into single weighted fusion. In retrieval_engine.py, replace aggregate_pools with db.get_sentences_by_node, add conversation_state parameter.
**Tech Stack:** Python, psycopg2, pgvector, numpy, DeepSeek API

---

### Task 1: F005 — Add embedding computation to _score_sentence_pool

**Files:**
- Modify: `src/f005_context_scoring/score_tree.py`
- Modify: `src/tests/f005_context_scoring/test_score_tree.py`

**Step 1: Write failing test** — test that `_score_sentence_pool()` stores `_context_vec` on each sentence when `embed_texts` is provided; test that `_context_vec` is a 768-dim list
**Step 2: Run test to verify it fails**
**Step 3: Implement** — In `_score_sentence_pool()`: after computing conversation_context, batch all script_texts, call `embed_texts()` (optional param), store as `_context_vec` on each sentence
**Step 4: Run test to verify it passes**
**Step 5: Commit**

---

### Task 2: F005 — Add PostgreSQL upsert to write_scored_tree

**Files:**
- Modify: `src/f005_context_scoring/score_tree.py`
- Modify: `src/tests/f005_context_scoring/test_score_tree.py`

**Step 1: Write failing test** — test that `write_scored_tree(db=mock_db)` calls `db.upsert_nodes()` and `db.upsert_sentences()`; test that each sentence gets `context_vec_id = script_id` in JSON output; test that `_context_vec` is NOT in JSON output (backward compat)
**Step 2: Run test to verify it fails**
**Step 3: Implement** — In `write_scored_tree()`: after scoring, walk tree to collect all nodes and sentences. Call `db.upsert_nodes()` and `db.upsert_sentences()` (including embedding). Pop `_context_vec` from each sentence, add `context_vec_id = script_id`. Also populate `taxonomy_keywords` from `state_keywords.json`.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

---

### Task 3: F006 — Replace context similarity with vector similarity in retrieval_ranking.py

**Files:**
- Modify: `src/f006_retrieval_engine/retrieval_ranking.py`
- Modify: `src/tests/f006_retrieval_engine/test_retrieval_ranking.py`

**Step 1: Write failing test** — test `compute_vec_similarity()` returns dict of script_id → float scores; test `RANKING_WEIGHTS` dict has correct keys and sums to 1.0; test that `compute_context_similarity` is no longer importable from the module
**Step 2: Run test to verify it fails**
**Step 3: Implement** — Remove `compute_context_similarity()`, `_rank_limited()`, `RANKING_STRATEGY`. Add `RANKING_WEIGHTS = {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15}`. Add `compute_vec_similarity(query_vec, candidate_script_ids, db)` that fetches vectors from PostgreSQL and computes cosine similarity.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

---

### Task 4: F006 — Unified weighted fusion ranking

**Files:**
- Modify: `src/f006_retrieval_engine/retrieval_ranking.py`
- Modify: `src/tests/f006_retrieval_engine/test_retrieval_ranking.py`

**Step 1: Write failing test** — test `rank_sentences()` computes `final_score = 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`; test sorted by final_score DESC; test `final_score` field on each sentence; test `_rank_full` and `_rank_limited` are gone
**Step 2: Run test to verify it fails**
**Step 3: Implement** — Rewrite `rank_sentences()` as single unified fusion: compute vec_score via `compute_vec_similarity()`, compute bg_boost via existing `compute_bg_boost()`, compute final_score, sort DESC. Remove `_rank_full()`.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

---

### Task 5: F006 — Update retrieval_engine.py for PostgreSQL retrieval + conversation_state

**Files:**
- Modify: `src/f006_retrieval_engine/retrieval_engine.py`
- Modify: `src/tests/f006_retrieval_engine/test_retrieval_engine.py`

**Step 1: Write failing test** — test `recommend()` accepts `conversation_state` parameter; test output has `vec_score`, `final_score`, `conversation_state` keys; test output does NOT have `conversation_context_similarity` or `strategy` keys; test candidates come from `db.get_sentences_by_node()` when db is provided
**Step 2: Run test to verify it fails**
**Step 3: Implement** — Remove import of `compute_context_similarity`. Add imports of `compute_vec_similarity`, `RANKING_WEIGHTS`, `SentenceDB`, `embed_single`. Add `conversation_state` parameter to `recommend()`. Replace `aggregate_pools(nodes)` with `db.get_sentences_by_node(node_id)` when db provided. Update output dict.
**Step 4: Run test to verify it passes**
**Step 5: Commit**
