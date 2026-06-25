# Feature-Wise Implementation Plan: Debt Collection Script Recommendation System

## Overview

Decompose the phase-based plan into independently developable features. Each feature states its goal, passing criteria, and dependencies. All new code lives under `/src`. Data input is `/data/output_manual.py`.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Database | **PostgreSQL + pgvector** | One database for metadata + vectors + FTS; ACID; mature; handles 50K+ records trivially |
| Embeddings | **DeepSeek embedding API** | Client already exists in `infra/llm_client.py` |
| SAS (Script Analogy Score) | **TF-IDF cosine** | Char bigram TF-IDF within sentence pool — unchanged |
| Conversation context similarity | **Vector cosine via pgvector** | Replaces char-ngram TF-IDF; captures semantic meaning ("没钱" ≈ "经济困难") |
| Full-text search | **PostgreSQL tsvector + GIN** | Keyword-based state extraction fallback; fuzzy matching on script_text |
| Ranking | **Weighted fusion** | `0.40×win_rate + 0.30×vec_score + 0.15×sas + 0.15×bg_boost` |
| State extraction | **LLM-first (DeepSeek)** | LLM is primary extraction; keyword scan via tsvector as fallback |
| Conversation state | **Accumulated across turns** | Caller passes in previously extracted states; system appends new extractions; used for path matching |
| Candidate retrieval | **PostgreSQL** | Sentences stored in PG, retrieved by node_id with bitmask filter + vector rank in single query |
| API | **FastAPI** | Already in `pyproject.toml` dependencies |

---

## Dependency Graph

```
F000 ──► F001 ──► F003 ──► F004 ──► F005 ──► F006 ──► F008
                                     │              │
                              F007 ──┘              │
                                     │              │
                              F009 ─────────────────┘
```

> **F002 removed** (ADR-009): LLM State Extraction eliminated. F001's manual annotations (493/805 turns) provide sufficient state coverage. Downstream features handle unlabeled turns gracefully.

---

## F000: State Keyword Discovery

**Depends on:** None

**Goal:** Analyze all turns across 31 records to discover the actual state keyword landscape from data. Group same-meaning keywords into canonical groups (e.g. "没钱", "经济困难" → group `financial_hardship`). Discover **fact groups**, **emotion groups**, **collector action groups**, and **willingness levels** (count determined by data clustering). Include suggested domain-common keywords not observed in 31 records. Output taxonomy to `/src/state_keywords.json` that F002 will consume.

**Passing criteria:**
- `state_keywords.json` contains `facts`, `emotions`, `willingness_levels`, `collector_actions` arrays
- Each group has `group_name`, `keywords` (variant list), `frequency`, `example_turn`, `source` ("observed" or "suggested")
- Groups sorted by frequency descending; suggested after observed
- Total observed fact groups ≥ 5, total observed emotion groups ≥ 5, total observed collector action groups ≥ 4
- Willingness levels ordered most resistant → most cooperative; count is data-driven
- Each willingness level has `level`, `definition`, `boundary`, `example_turns` (≥2 with `text` + `reason`)
- Every `example_turn` traces to an actual turn in `/data/output_manual.py`
- Suggested domain keywords included with `source: "suggested"`, `frequency: 0`

---

## F001: Data Schema Alignment

**Depends on:** F000

**Goal:** Map raw records from `/data/output_manual.py` to SOP-aligned schema — derive `turns_annotated`, `reward` (null), `state_transitions` (empty), and `context` constraint dict from `customer_info` fields. Output to `/src/f001_schema_alignment/output_aligned.py`.

**Passing criteria:**
- All 31 records present
- Every record has `turns_annotated`, `reward`, `state_transitions`, `context`
- All 9 context fields populated (no nulls in required fields)
- Original dialog data preserved verbatim

---

## F002: ~~LLM State Extraction~~ REMOVED

**Status:** Removed per ADR-009. F001's manual annotations (493/805 turns) are sufficient. Downstream features handle missing `state` on unlabeled turns gracefully.

---

## F003: Reward Labeling

**Depends on:** F001

**Goal:** Determine R ∈ {0, 1} per conversation — LLM detects repayment commitment triggers in final turns, performs counterfactual verification to credit the preceding collector action, cross-validates against `plan_evaluation`. Output to `/src/f003_reward_labeling/output_rewarded.py`.

**Passing criteria:**
- Every record has `reward` ∈ {0, 1}
- Every R=1 record has `reward_evidence` and `reward_action_credit`
- R=1 records consistent with `plan_evaluation` (mismatches flagged as warnings)
- No R=0 record has `reward_action_credit`

---

## F004: Decision Tree Construction

**Depends on:** F003

**Goal:** Build state-transition decision tree from annotated conversations — extract paths `S₀ → a₀ → S₁ → a₁ → ... → Sₙ`, merge identical/near-identical state sequences, accumulate historical collector sentences at each node, implement fallback via progressive tag removal. Output to `/src/decision_tree.json`.

**Passing criteria:**
- Tree has root node with `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`
- All 31 conversations represented (every call_id in at least one `source_call_ids`)
- Keywords lexicographically sorted at every node

---

## F005: Context Tagging, Quality Scoring & Embedding

**Depends on:** F004

**Goal:** Tag each sentence with `bg_constraints` from source conversation's customer profile, encode as bitmask for O(1) filtering. Compute HWR (node-level aggregation with sentence-level blending) and SAS (TF-IDF cosine similarity). Compute and store vector embeddings for `conversation_context` via pgvector. Write all sentence and node data to PostgreSQL with tsvector for FTS. UC and CSI deferred. Output tree structure to `/src/decision_tree_scored.json` (backward compat), all data to PostgreSQL.

**Changes from previous F005:**
- **Added**: Embedding computation for `conversation_context` at build time
- **Added**: PostgreSQL `nodes` table — path signatures for O(1) hash lookup
- **Added**: PostgreSQL `sentences` table — all metadata + embedding vector + tsvector for FTS
- **Added**: pgvector `embedding` column (vector(768)) with HNSW index
- **Added**: GIN index on tsvector for full-text keyword search
- **Unchanged**: Bitmask encoding, HWR/win_rate, SAS via TF-IDF

**PostgreSQL schema:**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE nodes (
  id              SERIAL PRIMARY KEY,
  state_id        TEXT NOT NULL,
  path_signature  TEXT NOT NULL UNIQUE,
  branch_key      JSONB,
  parent_id       INTEGER REFERENCES nodes(id),
  depth           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_nodes_path_sig ON nodes(path_signature);

CREATE TABLE sentences (
  id                  SERIAL PRIMARY KEY,
  script_id           TEXT NOT NULL UNIQUE,
  node_id             INTEGER NOT NULL REFERENCES nodes(id),
  script_text         TEXT NOT NULL,
  bg_bitmask_int      INTEGER NOT NULL DEFAULT 0,
  win_rate            REAL NOT NULL DEFAULT 0,
  sas                 REAL NOT NULL DEFAULT 0,
  bg_background       JSONB,
  conversation_context TEXT,
  embedding           vector(768),
  script_tsv          tsvector GENERATED ALWAYS AS (to_tsvector('simple', script_text)) STORED
);
CREATE INDEX idx_sentences_node_id ON sentences(node_id);
CREATE INDEX idx_sentences_bg_bitmask ON sentences(bg_bitmask_int);
CREATE INDEX idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_sentences_tsv ON sentences USING gin (script_tsv);
```

**Passing criteria:**
- Every sentence has `bg_constraints` dict with all bitmask fields
- Every sentence has `bg_bitmask_int` integer
- Every sentence has `win_rate` (blended HWR) ≥ 0
- Every sentence has `sas` ≥ 0
- PostgreSQL `sentences` row count equals total sentence count in scored tree
- PostgreSQL `nodes` row count equals total node count in scored tree
- Every `embedding` column has dimension 768 and non-zero norm
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset
- HNSW index returns same top-K as brute-force cosine (within epsilon)
- tsvector FTS finds sentences containing known keywords

---

## F006: Retrieval & Ranking Engine

**Depends on:** F005

**Goal:** Build `recommend()` function — given conversation state (accumulated facts/emotions/actions from prior turns) + current customer utterance + context, extract new state via LLM, merge into conversation state, compute path signature, look up node via hash index (O(1)), retrieve candidates from PostgreSQL with bitmask filter, compute vector similarity via pgvector, rank by weighted fusion, return top-1 script.

**Changes from previous F006:**
- **Replaced**: `compute_context_similarity` (char-ngram TF-IDF) → pgvector cosine similarity
- **Replaced**: `_rank_limited` / `_rank_full` dual strategy → single unified weighted fusion ranking
- **Replaced**: In-memory `node.sentence_pool` candidate retrieval → PostgreSQL `SELECT ... WHERE node_id = ?`
- **Added**: `RANKING_WEIGHTS` dict: `{win_rate: 0.40, vec_score: 0.30, sas: 0.15, bg_boost: 0.15}`
- **Added**: `vec_score` and `final_score` in output
- **Added**: Conversation state accumulation — new extractions merged into existing state
- **Removed**: `conversation_context_similarity` field (replaced by `vec_score`)
- **Removed**: `strategy` field (single unified path)

**Architecture:** No graph traversal at retrieval time. The decision tree is a **key-value lookup problem**: each node's position is fully determined by its path signature (e.g., `financial_hardship|pleading|pressure`). Precompute `path_signature` for every node at build time. At retrieval time, compute the signature from the accumulated conversation state and do a single hash lookup. This is O(1) regardless of tree size.

**Retrieval pipeline:**
1. **State extraction**: LLM (DeepSeek) extracts facts + emotions + actions from customer utterance, given taxonomy context
2. **State accumulation**: Merge new extractions into conversation state (deduplicated, ordered)
3. **Path computation**: Derive path signature from accumulated conversation state (deterministic)
4. **Node lookup**: Hash map `signature → node_id` — O(1)
5. **Fallback**: If exact signature miss, strip tags progressively and retry — O(depth) worst case
6. **Candidate retrieval + bitmask filter**: `SELECT ... FROM sentences WHERE node_id = ? AND (bg_bitmask_int & ?) = bg_bitmask_int` — single PG query
7. **Vector similarity**: pgvector `<=>` operator or cosine in Python after fetching embeddings — O(pool_size)
8. **Rank**: Weighted fusion `0.40×win_rate + 0.30×vec_score + 0.15×sas + 0.15×bg_boost` — O(pool_size log pool_size)
9. **Return**: Top-1 script + updated conversation state

**Hybrid retrieval SQL (single query for steps 6+7):**

```sql
SELECT script_id, script_text, win_rate, sas, bg_bitmask_int, bg_background,
       1 - (embedding <=> $query_vec) AS vec_score
FROM sentences
WHERE node_id = $node_id
  AND (bg_bitmask_int & $query_bitmask) = bg_bitmask_int
ORDER BY (0.40 * win_rate + 0.30 * (1 - (embedding <=> $query_vec)) + 0.15 * sas) DESC
LIMIT 1;
```

**Passing criteria:**
- `recommend()` returns `{ script_text, script_id, state_id, win_rate, vec_score, sas, final_score, confidence, conversation_state, ranking_weights, fallbacks }`
- Conversation state accumulates correctly across turns (no duplicates, ordered)
- Path signature derived from accumulated conversation state
- Exact state match returns sentence from matched node via PostgreSQL lookup
- Fallback (tag removal) returns sentence from sub-state node
- Context filtering excludes sentences with incompatible bitmask
- Vector similarity computed via pgvector, not char-ngram TF-IDF
- Ranking uses weighted fusion with configurable weights
- Retrieval latency < 200ms (LLM extraction + PG query + rank)

---

## F007: Scaling Architecture Design

**Depends on:** F005

**Goal:** Document migration path from 31 → 100,000+ nodes. Retrieval is O(1) hash lookup regardless of tree size (F006 architecture). Scaling challenges are storage, build-time, and index maintenance — not retrieval latency.

**Scaling dimensions:**

| Dimension | Current (31 records) | Target (50K+ records) | Solution |
|-----------|---------------------|----------------------|----------|
| Nodes | 315 | 100,000+ | Tree grows with record diversity, not linearly with records |
| Node storage | JSON file | PG `nodes` table with `path_signature` B-tree index | O(log N) lookup |
| Sentence storage | JSON in-memory pools | PG `sentences` table with `node_id` index | Filter + rank in SQL |
| Vector search | char-ngram TF-IDF | pgvector HNSW index | O(log N) approximate KNN |
| Full-text search | None | PG tsvector + GIN index | BM25-ish keyword search |
| Build time | ~30s (with LLM merge) | Batch LLM + incremental rebuild | Only rebuild affected subtrees on new data |
| Child lookup | Linear scan of `children[]` | Hash map `branch_key → child` per node | O(1) child resolution |
| Context filter | Python loop | PG bitwise op: `bg_bitmask_int & ? = bg_bitmask_int` | Index + SQL filter |
| Retrieval | JSON load + tree walk | Hash lookup + PG SELECT + pgvector | O(1) + O(pool_size) |

**Architecture at scale:**

```
Build time:
  records → merge_collector_turns → build_tree → score_tree → embed → PostgreSQL

Storage (PostgreSQL + pgvector):
  nodes(id, state_id, path_signature, branch_key, parent_id, depth)
  sentences(id, node_id, script_text, bg_bitmask_int, win_rate, sas,
            embedding vector(768), script_tsv tsvector, ...)
  Index: nodes.path_signature UNIQUE
  Index: sentences.node_id
  Index: sentences.embedding HNSW (vector_cosine_ops)
  Index: sentences.script_tsv GIN

Retrieval (hot path):
  accumulated_state → path_signature → hash_index[signature] → node_id
         → SELECT from sentences WHERE node_id = ? AND bitmask_filter
         → ORDER BY weighted_fusion(win_rate, vec_score, sas) DESC LIMIT 1
```

**Migration steps:**

1. **JSON → PostgreSQL**: Write `build_tree` output to PG instead of JSON. Add `path_signature` column. Same retrieval logic, different storage.
2. **Hash index for child lookup**: Replace `children[]` linear scan with `dict[branch_key] → child` per node. O(1) child resolution during tree build and retrieval.
3. **Incremental rebuild**: On new records, only rebuild affected subtrees (identified by changed branch keys). Cache unchanged subtrees.
4. **Batch LLM merge**: Process merge candidates in batches (current: sequential). Use merge cache to avoid re-calling LLM for unchanged groups.
5. **pgvector HNSW tuning**: Adjust `ef_construction` and `m` parameters for recall/latency tradeoff at scale.

**Managed hosting options:**
- **Supabase** — PostgreSQL + pgvector + pg_net + realtime. Free tier handles 50K rows easily.
- **Neon** — Serverless Postgres with branching. Auto-suspend when idle. pgvector supported.
- **Self-hosted** — `docker run postgres:16-pgvector` for on-premise deployment.

**Passing criteria:**
- Covers all 5 migration steps
- Each step has before/after architecture
- Retrieval latency target: < 50ms at 100K nodes (hash + PG query, excluding LLM state extraction)
- PostgreSQL DDL specified
- Build-time strategy for incremental rebuild documented

---

## F008: State Extraction

**Depends on:** F006

**Goal:** Implement LLM-first state extraction — DeepSeek LLM extracts facts/emotions/actions from customer utterance given the taxonomy. Keyword scan via PostgreSQL tsvector available as fallback if LLM fails or is unavailable. Output to `/src/f006_retrieval_engine/state_extraction.py`.

**Functions:**
- `extract_state_llm(utterance, taxonomy) → {facts, emotions, actions, confidence, method: "llm"}`
  - DeepSeek call with taxonomy as prompt context
  - LLM returns canonical group names from taxonomy
  - confidence from LLM self-assessment or heuristic
- `extract_state_keyword(utterance, taxonomy) → {facts, emotions, actions, confidence, method: "keyword"}`
  - PostgreSQL tsvector FTS: `SELECT group_name FROM taxonomy_keywords WHERE tsv @@ to_tsquery(utterance_tokens)`
  - Fallback only — used when LLM is unavailable
- `extract_state(utterance, taxonomy) → {facts, emotions, actions, confidence, method}`
  - LLM-first; if LLM succeeds → return LLM result
  - else → keyword fallback via tsvector
- `merge_state(existing_state, new_extraction) → updated_state`
  - Merge new extractions into existing conversation state
  - Deduplicate facts/emotions/actions (set semantics)
  - Preserve insertion order (first-seen order)

**Passing criteria:**
- LLM extractor returns valid taxonomy group names for known utterances
- Keyword extractor returns non-empty facts/emotions/actions for known utterances
- LLM-first: `extract_state` calls LLM first, keyword only on failure
- `merge_state` deduplicates: merging same fact twice yields single entry
- `merge_state` preserves order: first-seen items stay first
- `method` field correctly indicates "llm" or "keyword"

---

## F009: REST API

**Depends on:** F006, F008

**Goal:** Serve end-to-end recommendation via FastAPI. Input: customer utterance + conversation context (past ~100 words) + conversation state (accumulated from prior turns) + customer profile. Output: top-1 recommended script + updated conversation state. Output to `/src/api/server.py`.

**Endpoint:**

```
POST /recommend
Body: {
  customer_utterance: str,
  conversation_context: str,          // past ~100 words of dialog
  conversation_state: {               // accumulated from prior turns
    facts: list[str],                 // e.g. ["financial_hardship"]
    emotions: list[str],              // e.g. ["pleading"]
    actions: list[str]                // e.g. ["empathy"]
  },
  context: {                          // customer profile
    age, gender, industry, has_auto_loan, has_mortgage,
    has_negotiation_history, social_insurance_stable,
    credit_rating_good, card_restricted, is_cash_out_customer,
    has_complaint_history, has_legal_tools, is_negotiation_brain_customer
  }
}
→ 200: {
  script_text: str,
  script_id: str,
  state_id: str,
  win_rate: float,
  vec_score: float,
  sas: float,
  final_score: float,
  confidence: float,
  extraction_method: "llm" | "keyword",
  conversation_state: {               // updated — caller passes back on next turn
    facts: list[str],
    emotions: list[str],
    actions: list[str]
  },
  ranking_weights: dict,
  fallbacks: list[str],
  latency_ms: int
}
```

**Pipeline wiring:**
1. `extract_state(customer_utterance, taxonomy)` → new facts, emotions, actions, method
2. `merge_state(conversation_state, new_extraction)` → updated conversation state
3. Compute path signature from updated conversation state
4. `hash_index[signature]` → node_id (O(1), with fallback)
5. PostgreSQL query: candidates with bitmask filter + vector similarity + ranking in single SQL
6. Return top-1 + updated conversation state

**Conversation state lifecycle:**
- First turn: `conversation_state = {facts: [], emotions: [], actions: []}`
- Each turn: new extractions merged in, updated state returned
- Caller is responsible for passing updated state back on next turn
- This is how `inherited_facts` are built — incrementally across the dialog

**Passing criteria:**
- API returns 200 with valid recommendation for known inputs
- API returns appropriate error for missing/invalid inputs
- `conversation_state` in response includes merged state from input + new extraction
- `latency_ms` reflects actual processing time
- `extraction_method` indicates which path was taken ("llm" or "keyword")
- All ranking weights present in response
- API starts via `uvicorn src.api.server:app`

---

## Edit Sequence

Ordered by dependency. Each edit is a concrete, testable change.

### Edit 1: Add dependencies to `pyproject.toml`

Add `psycopg2-binary>=2.9`, `pgvector>=0.3`, `numpy>=1.26` to `[project] dependencies`.

### Edit 2: New file — `src/infra/db.py`

PostgreSQL + pgvector database client.

```python
class SentenceDB:
    __init__(self, dsn: str = "postgresql://...")
    create_tables(self)                                          # CREATE EXTENSION vector; CREATE TABLE nodes/sentences; CREATE INDEX
    upsert_nodes(self, nodes: list[dict])                        # bulk insert nodes with path_signature
    upsert_sentences(self, sentences: list[dict])                # bulk insert sentence metadata + embedding + tsvector
    get_sentences_by_node(self, node_id: int) → list[dict]      # candidate retrieval
    get_node_by_signature(self, path_signature: str) → dict     # node lookup
    search_similar(self, query_vec, node_id, query_bitmask, limit=50) → list[dict]  # hybrid: bitmask filter + vector rank
    keyword_search(self, query_text: str, limit=20) → list[dict]                   # tsvector FTS fallback
```

### Edit 3: New file — `src/infra/embeddings.py`

Embedding client wrapping DeepSeek embed API.

```python
embed_texts(texts: list[str]) → list[list[float]]    # batch embed via DeepSeek
embed_single(text: str) → list[float]                 # single embed (for query-time)
```

### Edit 4: Modify `src/f005_context_scoring/score_tree.py`

Add embedding computation + PostgreSQL writes at build time:
- Import `embed_texts` from `infra.embeddings`
- Import `SentenceDB` from `infra.db`
- In `_score_sentence_pool`: embed `conversation_context` for each sentence, store `embedding` field
- In `write_scored_tree`: after scoring, upsert all nodes/sentences to PostgreSQL (including embeddings); pop raw vectors from JSON output

No changes to `scoring_metrics.py` (SAS stays TF-IDF).

### Edit 5: Modify `src/f006_retrieval_engine/retrieval_ranking.py`

- Remove `compute_context_similarity` (char-ngram TF-IDF, ~25 lines)
- Remove `_rank_limited` function
- Add `compute_vec_similarity` using pgvector cosine (via `SentenceDB.search_similar`)
- Add `RANKING_WEIGHTS = {win_rate: 0.40, vec_score: 0.30, sas: 0.15, bg_boost: 0.15}`
- Rewrite `_rank_full` as unified weighted fusion ranking using `RANKING_WEIGHTS`
- Update `rank_sentences` to single path (no strategy dispatch)

### Edit 6: Modify `src/f006_retrieval_engine/retrieval_engine.py`

- Update imports: remove `compute_context_similarity`, add `compute_vec_similarity`, `RANKING_WEIGHTS`
- Replace in-memory `aggregate_pools(nodes)` with `SentenceDB.get_sentences_by_node(node_id)`
- Add `conversation_state` parameter to `recommend()` — accumulated state from prior turns
- Add `merge_state()` call — merge new extraction into conversation state
- Update `recommend()` output: add `vec_score`, `final_score`, `conversation_state`; replace `conversation_context_similarity` → `vec_score`; replace `strategy` → `ranking_weights`

### Edit 7: New file — `src/f006_retrieval_engine/state_extraction.py`

LLM-first state extraction:
- `extract_state_llm(utterance, taxonomy)` — DeepSeek call (primary)
- `extract_state_keyword(utterance, taxonomy)` — PostgreSQL tsvector FTS (fallback)
- `extract_state(utterance, taxonomy)` — LLM-first, keyword fallback on failure
- `merge_state(existing_state, new_extraction)` — deduplicated accumulation

### Edit 8: New file — `src/api/server.py`

FastAPI app with `POST /recommend` wiring the full pipeline:
LLM state extraction → state accumulation → path signature → hash lookup → PostgreSQL hybrid query (bitmask + vector + rank) → output with updated conversation state

### Edit 9: Regenerate `decision_tree_scored.json` + populate PostgreSQL

Re-run `score_tree.py` to produce updated JSON (backward compat) and populate PostgreSQL tables with nodes, sentences, embeddings, and tsvector data.

### Edit 10: Update tests

| Test file | Change |
|---|---|
| `test_score_tree_scoring.py` | Add assertion for embedding field; verify PG row counts |
| `test_retrieval_ranking.py` | Replace `compute_context_similarity` tests with `compute_vec_similarity` tests; add `RANKING_WEIGHTS` tests |
| `test_retrieval_engine.py` | Update output field checks: `vec_score` + `final_score` + `conversation_state`; test PG-backed candidate retrieval |
| New: `test_state_extraction.py` | Test LLM extractor, keyword FTS fallback, `merge_state` dedup/order |
| New: `test_db.py` | Test `SentenceDB` upsert/search_similar/keyword_search |
| New: `test_embeddings.py` | Test `embed_texts`, `embed_single` |
| New: `test_api.py` | Test `POST /recommend` endpoint, conversation state accumulation across turns |
