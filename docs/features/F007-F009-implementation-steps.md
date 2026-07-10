# F007–F009 Implementation Steps

Feature-by-feature breakdown of what to modify and what to build, ordered by dependency. Each step is independently testable. This is the concrete file-level edit playbook backing F007, F007b, F008, and F009.

**Legend:**
- **MODIFY** = change existing file
- **NEW** = create new file
- **REGENERATE** = re-run existing script to produce updated output
- Status: ✅ exists and works, 🔧 needs modification, ❌ does not exist

**Step → feature mapping:** Steps 1-3 → F007, Steps 4-6 → F007b, Step 7 → F008, Steps 8-9 → F009, Steps 9-10 → F007b (regenerate) + all (tests), Step 12 → docs.

---

## Step 1: Add Dependencies

**File:** `pyproject.toml` — MODIFY

**What:** Add PostgreSQL + pgvector + numpy dependencies.

**After:**
```python
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.0",
    "openai>=1.30",
    "python-dotenv>=1.0",
    "python-socketio>=5.11",
    "httpx>=0.27",
    "websockets>=12.0",
    "psycopg2-binary>=2.9",
    "pgvector>=0.3",
    "asyncpg>=0.29",
    "numpy>=1.26",
]
```

**Verify:** `pip install -e .` succeeds.

---

## Step 2: Embedding Client

**File:** `src/f007_infrastructure/embeddings.py` — NEW

**What:** bge-m3 embedding client via Ollama (OpenAI-compatible API). See ADR-024.

```python
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed via bge-m3/Ollama. Returns 1024-dim vectors."""

def embed_single(text: str) -> list[float]:
    """Single embed for query-time. Returns 1024-dim vector."""
```

**Config:** `EMBEDDING_MODEL` (default `bge-m3`), `EMBEDDING_BASE_URL` (default `http://localhost:11434/v1`), `EMBEDDING_API_KEY`, `EMBEDDING_DIM` (default 1024).

**Verify:** `embed_single("测试")` returns list of 1024 floats with non-zero norm.

---

## Step 3: PostgreSQL Database Client

**File:** `src/f007_infrastructure/db.py` — NEW

**What:** PostgreSQL + pgvector client for sentence and node storage.

```python
class SentenceDB:
    def __init__(self, dsn: str)
    def create_tables(self)                                          # CREATE EXTENSION vector; CREATE TABLE nodes/sentences/taxonomy_keywords
    def upsert_nodes(self, nodes: list[dict])                        # bulk insert nodes with path_signature
    def upsert_sentences(self, sentences: list[dict])                # bulk insert sentence metadata + embedding + tsvector
    def get_sentences_by_node(self, node_id: int) -> list[dict]      # candidate retrieval
    def get_node_by_signature(self, path_signature: str) -> dict     # node lookup
    def search_similar(self, query_vec, node_id, query_bitmask, limit=50) -> list[dict]  # hybrid: bitmask filter + vector rank
    def keyword_search(self, query_text: str, limit=20) -> list[dict]                   # tsvector FTS fallback
```

**Schema** (from `full_processing.md`):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
  embedding           vector(1024),
  script_tsv          tsvector GENERATED ALWAYS AS (to_tsvector('simple', script_text)) STORED
);
CREATE INDEX idx_sentences_node_id ON sentences(node_id);
CREATE INDEX idx_sentences_bg_bitmask ON sentences(bg_bitmask_int);
CREATE INDEX idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_sentences_tsv ON sentences USING gin (script_tsv);
CREATE INDEX idx_sentences_script_text_trgm ON sentences USING gin (script_text gin_trgm_ops);

CREATE TABLE taxonomy_keywords (
  id          SERIAL PRIMARY KEY,
  group_name  TEXT NOT NULL,
  category    TEXT NOT NULL,
  keyword     TEXT NOT NULL,
  frequency   INTEGER NOT NULL DEFAULT 0,
  tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', keyword)) STORED
);
CREATE INDEX idx_taxonomy_tsv ON taxonomy_keywords USING gin (tsv);
CREATE INDEX idx_taxonomy_group ON taxonomy_keywords(group_name, category);
```

**Verify:** `db.create_tables()` creates all tables and indexes. `db.upsert_nodes([{"state_id": "initial_contact", "path_signature": "", ...}])` inserts without error.

---

## Step 4: Modify F005 — Add Embedding + PostgreSQL Load

**File:** `src/f005_context_scoring/score_tree.py` — MODIFY

**What changes:**

1. Import `embed_texts` from `infra.embeddings` and `SentenceDB` from `infra.db`
2. In `_score_sentence_pool()`: after computing `conversation_context`, call `embed_texts()` for all sentences in the pool. Store embedding as `_context_vec` (temporary, not written to JSON).
3. In `write_scored_tree()`: after scoring, iterate tree to collect all nodes and sentences. Call `db.upsert_nodes()` and `db.upsert_sentences()` (including `embedding` column). Pop `_context_vec` from each sentence before writing JSON (keep JSON backward-compat, add `context_vec_id` = `script_id`).
4. Also populate `taxonomy_keywords` table from `state_keywords.json`.

**Files unchanged:** `src/f005_context_scoring/scoring_metrics.py` (SAS stays TF-IDF).

**Verify:** After running `score_tree.py`:
- `decision_tree_scored.json` has `context_vec_id` on each sentence
- PostgreSQL `nodes` table has 309 rows
- PostgreSQL `sentences` table has 782 rows with non-null `embedding` column
- PostgreSQL `taxonomy_keywords` table has rows from `state_keywords.json`

---

## Step 5: Modify F006 Retrieval Ranking — Vector Similarity + Unified Fusion

**File:** `src/f006_retrieval_engine/retrieval_ranking.py` — MODIFY

**What changes:**

1. **Remove** `compute_context_similarity()` (char-ngram TF-IDF, lines 36-80)
2. **Remove** `_rank_limited()` function (lines 111-131)
3. **Remove** `RANKING_STRATEGY = "limited"` constant
4. **Add** `RANKING_WEIGHTS = {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15}`
5. **Add** `compute_vec_similarity()`:
   ```python
   def compute_vec_similarity(query_vec: list[float], candidate_script_ids: list[str], db: SentenceDB) -> dict[str, float]:
       """Fetch candidate vectors from PostgreSQL, compute cosine similarity."""
       candidate_vecs = db.get_vectors(candidate_script_ids)
       scores = {}
       for sid, vec in candidate_vecs.items():
           dot = np.dot(query_vec, vec)
           norm = np.linalg.norm(query_vec) * np.linalg.norm(vec)
           scores[sid] = float(dot / norm) if norm > 0 else 0.0
       return scores
   ```
6. **Rewrite** `_rank_full()` as unified weighted fusion:
   - Compute `vec_score` via `compute_vec_similarity()` for all candidates
   - Compute `bg_boost` via existing `compute_bg_boost()`
   - Compute `final_score = 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`
   - Sort by `final_score` DESC
7. **Update** `rank_sentences()` to single path (no strategy dispatch):
   ```python
   def rank_sentences(pool, conversation_context="", query_bg=None, context_missing=False, db=None):
       # Always use unified fusion ranking
   ```

**Verify:** `rank_sentences()` produces deterministic output with `final_score` field. No reference to `compute_context_similarity` or `_rank_limited` remains.

---

## Step 6: Modify F006 Retrieval Engine — Conversation State + PostgreSQL Retrieval

**File:** `src/f006_retrieval_engine/retrieval_engine.py` — MODIFY

**What changes:**

1. **Remove** import of `compute_context_similarity`
2. **Add** imports of `compute_vec_similarity`, `RANKING_WEIGHTS`, `SentenceDB`, `embed_single`
3. **Add** `conversation_state` parameter to `recommend()`:
   ```python
   def recommend(inherited_facts, branch_key_values, query_bitmask,
                 conversation_context, query_bg, conversation_state=None,
                 strategy=RANKING_STRATEGY, tree=None, index=None, keyword_freq=None):
   ```
4. **Replace** `aggregate_pools(nodes)` with `db.get_sentences_by_node(node_id)` — candidates from PostgreSQL, not in-memory JSON
5. **Add** state accumulation: merge `conversation_state` with new extraction result
6. **Update** output dict:
   - Add `vec_score`, `final_score`, `conversation_state`
   - Remove `conversation_context_similarity`, `strategy`
   - Replace `strategy` with `ranking_weights`

**Verify:** `recommend()` returns dict with `vec_score`, `final_score`, `conversation_state` keys. No in-memory pool access.

---

## Step 7: State Extraction Module

**File:** `src/f008_state_extraction/state_extraction.py` — NEW

**What:** LLM-first state extraction with keyword fallback and state accumulation.

```python
def extract_state_llm(utterance: str, taxonomy: dict) -> dict:
    """DeepSeek call with taxonomy as prompt context.
    Returns {facts, emotions, actions, confidence, method: "llm"}"""

def extract_state_keyword(utterance: str, taxonomy: dict) -> dict:
    """PostgreSQL tsvector FTS fallback.
    Returns {facts, emotions, actions, confidence, method: "keyword"}"""

def extract_state(utterance: str, taxonomy: dict) -> dict:
    """LLM-first; keyword fallback on failure.
    Returns {facts, emotions, actions, confidence, method}"""

def merge_state(existing_state: dict, new_extraction: dict) -> dict:
    """Merge new extractions into existing conversation state.
    Deduplicate facts/emotions/actions (set semantics).
    Preserve insertion order (first-seen order)."""
```

**LLM prompt** (from `full_processing.md` Step 2.1): Sends the full taxonomy (facts, emotions, actions groups) to DeepSeek with the utterance, asks for JSON extraction.

**Keyword fallback**: `SELECT group_name, category FROM taxonomy_keywords WHERE tsv @@ to_tsquery(utterance_tokens)`.

**Verify:**
- `extract_state("我现在没钱还", taxonomy)` returns `{facts: ["financial_hardship"], ...}`
- `merge_state({facts: ["a"]}, {facts: ["b"]})` → `{facts: ["a", "b"]}`
- `merge_state({facts: ["a"]}, {facts: ["a"]})` → `{facts: ["a"]}` (dedup)

---

## Step 8: REST API Server

**File:** `src/f009_api_server/__init__.py` — NEW (empty)
**File:** `src/f009_api_server/server.py` — NEW

**What:** FastAPI app with `POST /recommend` endpoint.

```python
app = FastAPI()

@app.post("/recommend")
async def recommend_endpoint(req: RecommendRequest) -> RecommendResponse:
    """
    Pipeline:
      1. extract_state(customer_utterance, taxonomy)
      2. merge_state(conversation_state, new_extraction)
      3. Compute path signature from merged state
      4. hash_index[signature] → node_id (O(1), with fallback)
      5. db.search_similar(query_vec, node_id, query_bitmask) → candidates
      6. Rerank: 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost
      7. Return top-1 + updated conversation_state
    """
```

**Request model** (Pydantic, matching the F009 API contract):
```python
class ConversationState(BaseModel):
    facts: list[str]
    emotions: list[str]
    actions: list[str]

class RecommendRequest(BaseModel):
    customer_utterance: str
    conversation_context: str = ""
    conversation_state: ConversationState
    context: dict
```

**Startup** (lifespan): Load `hash_index` from PostgreSQL `nodes` table. Load `taxonomy` from `state_keywords.json`. Initialize `SentenceDB` and DeepSeek client.

**Verify:** `curl -X POST http://localhost:8000/recommend -d '...'` returns valid recommendation.

---

## Step 9: Socket.IO Integration

**File:** `src/f009_api_server/server.py` — MODIFY (add Socket.IO events)

**What:** Add Socket.IO event handlers per the F009 API contract:

| Event | Direction | Description |
|---|---|---|
| `start_session` | client→server | Initialize session with `cust_no` + `context`. Server creates session, returns `session_id`. |
| `customer_turn` | client→server | Send utterance + `conversation_context`. Server runs full pipeline, accumulates state automatically. |
| `collector_turn` | client→server | Record collector response. LLM extracts actions, accumulates into `conversation_state.actions`. |
| `end_session` | client→server | Close session, return full transcript. |
| `recommendation` | server→client | Push event when recommendation is ready (for async UI updates). |

**Session state** (in-memory dict keyed by `session_id`):
```python
sessions = {
    "sess_abc123": {
        "cust_no": "0100252354",
        "context": {},
        "conversation_state": {"facts": [], "emotions": [], "actions": []},
        "conversation_context_buffer": "",  # accumulated context text
        "transcript": [],
        "start_time": datetime
    }
}
```

**Verify:** Connect via Socket.IO client, emit `start_session` → `customer_turn` → `collector_turn` → `end_session`. Full transcript returned with accumulated state.

---

## Step 10: Regenerate Scored Tree + Populate PostgreSQL

**Action:** REGENERATE

**What:** Re-run `score_tree.py` to produce:
1. Updated `decision_tree_scored.json` with `context_vec_id` per sentence
2. PostgreSQL `nodes` table populated (309 rows)
3. PostgreSQL `sentences` table populated with embeddings (782 rows)
4. PostgreSQL `taxonomy_keywords` table populated

**Command:**
```bash
python3 -c "from f005_context_scoring.score_tree import write_scored_tree; write_scored_tree()"
```

**Verify:**
- `SELECT COUNT(*) FROM nodes` → 309
- `SELECT COUNT(*) FROM sentences` → 782
- `SELECT COUNT(*) FROM sentences WHERE embedding IS NOT NULL` → 782
- `SELECT COUNT(*) FROM taxonomy_keywords` > 0

---

## Step 11: Update Tests

### Existing tests — MODIFY

| Test file | What changes |
|---|---|
| `test_score_tree_scoring.py` | Add assertion: every sentence has `context_vec_id` field |
| `test_retrieval_ranking.py` | Remove `compute_context_similarity` tests. Add `compute_vec_similarity` tests. Add `RANKING_WEIGHTS` validation tests. Add `final_score` computation tests. |
| `test_retrieval_engine.py` | Update output field checks: expect `vec_score` + `final_score` + `conversation_state`. Remove `conversation_context_similarity` checks. Remove `strategy` checks. Test PostgreSQL-backed candidate retrieval (mock `SentenceDB`). |

### New tests — NEW

| Test file | What |
|---|---|
| `src/tests/infra/test_embeddings.py` | Test `embed_texts()` returns correct dimensions. Test `embed_single()` returns non-zero norm. |
| `src/tests/infra/test_db.py` | Test `SentenceDB.create_tables()`. Test `upsert_nodes()` + `upsert_sentences()`. Test `get_sentences_by_node()`. Test `search_similar()` returns ranked results. Test `keyword_search()` returns taxonomy matches. |
| `src/tests/f006_retrieval_engine/test_state_extraction.py` | Test `extract_state_llm()` returns valid taxonomy groups. Test `extract_state_keyword()` returns matches. Test `extract_state()` LLM-first, keyword fallback. Test `merge_state()` dedup + order preservation. |
| `src/tests/api/test_recommend.py` | Test `POST /recommend` returns 200 with valid output. Test missing fields → 400. Test `conversation_state` accumulation across multiple calls. |
| `src/tests/api/test_socket.py` | Test `start_session` → `customer_turn` → `end_session` flow. Test state accumulation is automatic. Test `collector_turn` extracts actions. |

---

## Step 12: Update `src/README.md`

**File:** `src/README.md` — MODIFY

**What:** Add documentation for new modules:

- `f007_infrastructure/embeddings.py` — bge-m3 embedding client (Ollama)
- `f007_infrastructure/db.py` — PostgreSQL + pgvector database client
- `f008_state_extraction/state_extraction.py` — LLM-first state extraction
- `api/server.py` — FastAPI + Socket.IO server
- PostgreSQL schema reference
- New setup instructions (PostgreSQL connection, `pgvector` extension)

---

## Summary: What Exists vs. What Needs Work

| Component | Status | Step |
|---|---|---|
| `pyproject.toml` dependencies | ✅ FastAPI/Socket.IO present, ❌ psycopg2/pgvector/numpy missing | 1 |
| `f007_infrastructure/llm_client.py` | ✅ DeepSeek chat client | — |
| `f007_infrastructure/embeddings.py` | ❌ Does not exist | 2 |
| `f007_infrastructure/db.py` | ❌ Does not exist | 3 |
| `f005_context_scoring/score_tree.py` | ✅ Works, 🔧 needs embedding + PG load | 4 |
| `f005_context_scoring/scoring_metrics.py` | ✅ No changes needed | — |
| `f006_retrieval_engine/retrieval_ranking.py` | ✅ Works, 🔧 needs vector sim + unified ranking | 5 |
| `f006_retrieval_engine/retrieval_engine.py` | ✅ Works, 🔧 needs conversation_state + PG retrieval | 6 |
| `f008_state_extraction/state_extraction.py` | ❌ Does not exist | 7 |
| `api/server.py` | ❌ Does not exist | 8+9 |
| PostgreSQL database | ❌ Not provisioned | 3+10 |
| `decision_tree_scored.json` | ✅ Exists, 🔧 needs `context_vec_id` | 10 |
| Tests | ✅ Existing pass, 🔧 need updates + ❌ new tests missing | 11 |
| `src/README.md` | ✅ Exists, 🔧 needs new module docs | 12 |

## Links

- [F007-infra-layer.md](F007-infra-layer.md) — Steps 1-3
- [F007b-vector-retrieval-integration.md](F007b-vector-retrieval-integration.md) — Steps 4-6
- [F008-state-extraction.md](F008-state-extraction.md) — Step 7
- [F009-api-server.md](F009-api-server.md) — Steps 8-9
- [full_processing.md](../../full_processing.md) — Phase 2 pipeline + schema detail
- [ADR-024](../decisions/ADR-024-embedding-architecture.md) — bge-m3 embedding architecture

---

## Update Log

**2026-07-10 — Ranking weights updated (5-signal):** Steps 5–6 and the rerank step show the original 4-signal formula `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`. The current codebase uses a 5-signal formula: `0.35*win_rate + 0.25*vec_score + 0.10*sas + 0.10*bg_boost + 0.20*bitmask_score`. Weights are in `config.md` under `ranking_weights`.

**2026-07-10 — `full_processing.md` no longer in repo:** The link above to `../../full_processing.md` is broken — the file was removed. Phase 2 pipeline + schema detail is now documented in `SCBGE_GUIDELINE.md` Phase 2.
