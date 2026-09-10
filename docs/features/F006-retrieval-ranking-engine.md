---
REMOVED_FIELD_id: F006
name: Retrieval & Ranking Engine
status: complete
owner: agent
source: superseded (original spec plan_feature_base.md no longer in repo)
created: 2026-06-22
updated: 2026-07-30
merged: 2026-06-22
---

# F006: Retrieval & Ranking Engine

## Why

F005 produced a scored decision tree with bitmask-encoded context constraints and quality scores (HWR, SAS). But no function exists to consume this tree at retrieval time — given a real-time customer utterance + context, there is no way to find the right node, filter sentences by context, rank by quality, and return the best script. The retrieval engine closes the loop: data → tree → score → **recommend**.

## What

### Input

The retrieval engine receives:
- **Current customer turn**: the utterance text
- **Accumulated facts**: the set of facts identified so far (from `inherited_facts`)
- **Customer background**: `bg_bitmask` + `bg_background` (from F005's context tagging)
- **Conversation context**: candidate side = `context_window.conversation_turns` turns before the script (build time); query side = last 100 words via `_last_n_words` (request time)

### Architecture: DB Label Lookup → Aggregate Pool → Rank

The tree uses `inherited_facts` + `branch_key` values (both sorted alphabetically) as the node lookup key. Sorting ensures that permutations of keywords do not affect index matching. Multiple nodes sharing the same key represent the same conversational context at different tree positions — their sentences are aggregated into one candidate pool.

The retrieval engine:

1. **Matches by inherited_facts + branch_key** — emotions and willingness are NOT used to identify the node
2. **Queries database-backed node labels and sentence pools**; the API process does not load the full scored tree or indexes into `app.state`
3. **Ranks across the combined pool** using the dual-strategy ranker

### Node Lookup

Persist at build time:

```
nodes.labels: JSONB array with a GIN index; `path_signature` remains unique and indexed
```

Key = `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))`.

- `inherited_facts`: sorted alphabetically from the node's `inherited_facts` field
- `branch_key_values`: sorted alphabetically from the node's `branch_key` values (flattening lists: `{"facts": ["a", "b"]}` → `["a", "b"]`, `{"action": "closure"}` → `["closure"]`)
- `inherited_emotions`: sorted alphabetically from the node's `inherited_emotions` field

All three components are persisted in `nodes.labels` and queried with JSONB containment, so any permutation of input keywords produces the same candidate set. `inherited_emotions` is required: without it, emotional contexts can collide. Willingness is tracked in conversation state but **not** in the node key.

### Retrieval Pipeline

1. **Key computation**: Sort `inherited_facts` alphabetically + sort `branch_key` values alphabetically + sort `inherited_emotions` alphabetically → normalized DB label query
2. **Node lookup**: Query indexed `nodes.labels` with a bounded candidate limit
3. **Key fallback**: If exact key not in index, drop the least-frequent keyword from `inherited_facts` and retry — O(|facts|) worst case
4. **Pool retrieval**: Fetch each matched node's sentences from PostgreSQL by `node_id` — O(nodes × pool_size), bounded by the candidate limit
5. **Descend fallback**: If aggregated pool is empty, walk DOWN the tree — collect sentences from the nearest descendants with non-empty pools (BFS). All siblings at the same depth are included. E.g., if "unemployed" has no sentences, and its child "has kids" also has none, but "has kids" branches into "not married" and "married" which both have sentences → collect from both grandchildren.
6. **Key-drop fallback**: If descend fallback finds no sentences at any depth, drop the least-frequent keyword from `inherited_facts` and retry from step 1
6. **Soft bitmask scoring**: `bitmask_score = popcount(sb & qb) / popcount(sb)` (sentence with no constraints scores 1.0); partial matches rank lower, none are excluded (ADR-020 updated)
7. **Rank** (unified weighted fusion, ADR-024 — dual `limited`/`full` strategy deleted)
8. **Return**: Top-1 script

### Fallback Cascade

| # | Failure point | Cause | Fallback | Confidence impact |
|---|--------------|-------|----------|-------------------|
| 1 | **Key miss** | No DB node contains the normalized label set | Drop least-frequent keyword from `inherited_facts`, recompute the DB query, retry. Repeat until match or empty facts. | Each drop: −0.1 |
| 2 | **Empty pool — descend** | All matched nodes have empty `sentence_pool` but have children | Walk DOWN tree (BFS): collect sentences from nearest descendants with non-empty pools. All siblings at the same depth are included. E.g., "unemployed" → "has kids" (empty) → {"not married", "married"} (both have sentences) → collect from both. | Each level: −0.05 |
| 3 | **Empty pool — key drop** | Descend found no sentences at any depth | Drop least-frequent keyword from `inherited_facts`, retry from key lookup. | Each drop: −0.1 |
| 4 | **Bitmask partial match** | No sentence has a perfect bitmask overlap | Soft scoring: `bitmask_score = matched_bits / required_bits`; partial matches rank lower but are not excluded. Confidence reduced by `(1.0 − bitmask_score) × 0.1`. | −(1.0 − bitmask_score) × 0.1 |
| 5 | **Context missing** | No conversation context provided (first turn) | Skip context similarity ranking; set `vec_score = 0`, redistribute weight to `win_rate`. | −0.1 |
| 6 | **No sentences at all** | No sentences found at any depth, even at root | Return `None` with confidence 0.0. | 0.0 |

**Descend fallback detail**: BFS from matched nodes' children. At each depth level, check all nodes at that level. If any have non-empty pools, collect from all of them (siblings at the same depth are equally valid next steps). If all are empty, descend one more level. This handles the case where intermediate routing nodes (facts/emotions) have no sentences but their action children do.

**Confidence formula**:
```
confidence = 1.0
           − (fact_drops × 0.1)
           − (descend_levels × 0.05)
           − (bitmask_relaxations × 0.05)
           − (context_missing × 0.1)
```
Minimum: 0.0.

### Weighted Fusion Ranking

```python
RANKING_WEIGHTS = {
    "win_rate": 0.35,
    "vec_score": 0.25,
    "sas": 0.10,
    "bg_boost": 0.10,
    "bitmask_score": 0.20,
}
```

`final_score = 0.35 × win_rate + 0.25 × vec_score + 0.10 × sas + 0.10 × bg_boost + 0.20 × bitmask_score` (weights from `config.md`; dual `limited`/`full` strategy deleted by ADR-024)

**Fallback when embedding unavailable**: Set `vec_score = 0`, redistribute weight to `win_rate`. −0.1 confidence.

### Conversation Context Similarity (pgvector)

Each sentence has provenance in `sentence_sources(script_id, call_id)`; use it to look up original conversations and extract the `context_window.conversation_turns` turns immediately before the sentence was used. Store the resulting `conversation_context` with the sentence. At F005 build time, compute `embed(conversation_context)` via bge-m3 embedding API → 1024-dim vector stored in PostgreSQL `embedding` column with pgvector HNSW index.

At retrieval time:
1. **Query-side windowing**: the live `conversation_context` is truncated to its last 100 words via `_last_n_words()` (`src/f009_api_server/server.py`) before embedding, so `query_vec` represents a bounded recent context window regardless of how much history the caller sends. Applied at both embedding call sites (`/recommend` and `_run_turn`, the latter covering `/api/v1/recommend` and SocketIO `customer_turn`).
2. Compute `embed(query_context)` via bge-m3 embedding API for the windowed last-100-words context
3. **SQL-side scoring**: `db.search_by_nodes(query_vec, node_ids)` computes `vec_score = 1 - (embedding <=> query_vec)` in PostgreSQL using pgvector's cosine distance operator, filtered by `node_id = ANY(...)`, ordered by `vec_score DESC`
4. Use pre-computed `vec_score` as ranking signal in weighted fusion (no vector transfer to Python)

> **Window asymmetry**: the candidate side windows by **turn count** (`context_window.conversation_turns` = 20 turns, `score_tree.py:71`); the query side windows by **word count** (100 words, `server.py:_EMBED_CONTEXT_MAX_WORDS`). Both are bounded; units differ. Empty context short-circuits to a zero vector (Fallback 5).

See ADR-028 for rationale.

### bg_background Soft Boost (full strategy only)

| Match condition | Boost |
|----------------|-------|
| Exact industry match | +0.05 |
| Same education bracket | +0.02 |
| Similar debt range (within 50%) | +0.03 |
| Age within 10 years | +0.02 |

### Unified Fusion (ADR-024 — dual `limited`/`full` strategy deleted)

```python
def recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
    nodes = db.find_nodes_for_labels(labels, limit=32)     # step 1-3
    pool = db.get_sentences_by_node_ids(nodes)             # step 4-6
    for s in pool:
        s["bitmask_score"] = compute_bitmask_score(s.bg_bitmask_int, query_bitmask)  # soft (ADR-020)
    vec_score = compute_vec_score(pool, conversation_context)  # pgvector SQL-side (ADR-028)
    bg_boost = compute_bg_boost(...)                     # always applied
    final_score = 0.35 * win_rate + 0.25 * vec_score + 0.10 * sas + 0.10 * bg_boost + 0.20 * bitmask_score
    return top_by_final_score(pool)
```

### Output

```python
{
    "script_text": str,
    "script_id": str,
    "state_id": str,
    "win_rate": float,
    "vec_score": float,
    "sas": float,
    "final_score": float,
    "confidence": float,
    "strategy": str,
    "fallbacks": [str],
}
```

## Passing Criteria

- `recommend()` returns all fields in the output schema
- Fact set match returns aggregated pool from all sibling nodes
- Fallback (fact drop) returns pool from broader fact set
- Bitmask is a **soft ranking signal** (ADR-020 updated): `bitmask_score = matched_bits / required_bits`; partial matches rank lower, none are excluded
- Weighted fusion: `final_score = 0.35 × win_rate + 0.25 × vec_score + 0.10 × sas + 0.10 × bg_boost + 0.20 × bitmask_score` (weights from `config.md`; dual `limited`/`full` strategy deleted by ADR-024)
- `bg_boost` computed from profile similarity (industry, education, debt range, age)
- Confidence decreases with each fallback activated
- Retrieval latency < 150ms (indexed DB lookup + embed API + filter + sort)

## Acceptance Criteria

- [ ] `build_node_index()` creates index with 3-tuple keys: `(inherited_facts, branch_key_values, inherited_emotions)`
- [ ] Key is `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))` — permutation-insensitive
- [ ] `lookup_by_key(key, index)` returns all nodes matching key — O(1)
- [ ] `aggregate_pools(nodes)` collects all sentences from all matched nodes
- [ ] `add_conversation_context()` extracts and stores ~100-word context per sentence
- [ ] `recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg, strategy)` returns top-1 script with all output fields
- [ ] Exact key match returns aggregated pool (confidence=1.0, fallbacks=[])
- [ ] Fallback 1: key drop finds broader key (fallbacks=["key_drop"])
- [ ] Fallback 2: empty pool descends to nearest descendants with sentences (fallbacks=["descend"])
- [ ] Fallback 2: descend includes ALL siblings at the same depth (e.g., "not married" + "married")
- [ ] Fallback 3: descend finds nothing → key drop retry (fallbacks=["descend", "key_drop"])
- [ ] Fallback 4: bitmask relaxation when all sentences eliminated (fallbacks=["bitmask_relax"])
- [ ] Fallback 5: missing conversation context adjusts ranking (fallbacks=["context_missing"])
- [ ] Fallback 6: completely empty tree returns None (confidence=0.0)
- [ ] Bitmask soft scoring: `bitmask_score = matched_bits / required_bits`; partial matches rank lower, none excluded
- [ ] Weighted fusion: `final_score = 0.35 * win_rate + 0.25 * vec_score + 0.10 * sas + 0.10 * bg_boost + 0.20 * bitmask_score` (weights from `config.md`)
- [ ] `bg_boost` computed from profile similarity (dual `limited`/`full` strategy deleted by ADR-024)
- [ ] `vec_score` computed via pgvector cosine similarity
- [ ] `bg_background` soft boost computed correctly (industry +0.05, education +0.02, debt +0.03, age +0.02)
- [ ] Confidence formula: 1.0 − (key_drops×0.1) − (descend_levels×0.05) − (bitmask_relax×0.05) − (context_missing×0.1), minimum 0.0
- [ ] No LLM call for state extraction in hot path (state is pre-extracted by caller)
- [ ] bge-m3 embedding API call (via Ollama) for `vec_score` is the only API in hot path
- [ ] All keys reachable via some (inherited_facts, branch_key_values, inherited_emotions) pair
- [ ] Conversation context cosine similarity computed via pgvector on bge-m3 embeddings
- [ ] Output file: `/src/f006_retrieval_engine/retrieval_engine.py`

## Dependencies

- F005 (Context Tagging & Quality Scoring) — `decision_tree_scored.json` provides scored tree with bitmask + HWR + SAS + bg_background + inherited_facts

## Links

- ~~plan_feature_base.md~~ — original spec (no longer in repo; this doc is the authoritative source)

## Implementation Plan

See [implementation-plan.md](implementation-plan.md)

## Design Decisions

- **Node index by (inherited_facts, branch_key_values, inherited_emotions)**: The lookup key combines `inherited_facts`, `branch_key` values, and `inherited_emotions`, all sorted alphabetically. Sorting ensures permutation insensitivity. `inherited_emotions` is required: without it, 31 key collisions occur (e.g., `a:closure` under `['disappointment']` vs `['anger']` must not aggregate). The tree's own dedup identity (`tree_transforms.py:_make_identity`) already uses all three components.
- **Willingness not in key**: Willingness is a scalar (not a list) and represents the customer's current repayment intent. It's tracked in conversation state but doesn't determine node identity — it's a soft signal, not a branching dimension.
- **Aggregate pool from matching nodes**: When a label query matches multiple nodes, we pull sentences from all bounded candidates and rank across the combined pool. This gives the ranker more candidates without retaining the tree in process memory. Sentence provenance is served from `sentence_sources`; the JSON tree field remains an offline compatibility projection.
- **Descend fallback (not parent walk)**: When matched nodes have empty pools but have children, walk DOWN the tree (BFS) to find the nearest descendants with sentences. This is the correct direction — we've already matched the customer's facts, so the next scripts come from deeper in the tree (more specific actions/emotions), not from going back up. All siblings at the same depth are included: e.g., "unemployed" → "has kids" (empty) → {"not married", "married"} both contribute sentences.
- **Key-drop fallback after exhausted descend**: If descending finds no sentences at any depth (all descendants are routing-only nodes), then fall back to dropping a keyword from `inherited_facts` (least-frequent first) and retrying the lookup. This handles degenerate branches.
- **Bitmask as soft ranking signal (ADR-020 updated)**: `bitmask_score = matched_bits / required_bits` — partial matches rank lower but are not excluded. A sentence with no constraints scores 1.0.
- **Weighted fusion ranking**: `final_score = 0.35 × win_rate + 0.25 × vec_score + 0.10 × sas + 0.10 × bg_boost + 0.20 × bitmask_score`. All signals contribute simultaneously rather than staged sorting. `vec_score` from pgvector captures cross-conversation semantic similarity. Dual `limited`/`full` strategy deleted by ADR-024.
- **Context missing fallback**: Set `vec_score = 0`, redistribute weight to `win_rate`. −0.1 confidence.
- **bg_background as soft boost**: Shifts ranking toward profile-matching sentences without excluding viable ones.
- **SAS as intra-pool diversity**: Intra-pool similarity to highest-HWR sentence — redundancy avoidance, not relevance. Uses restricted-vocabulary jieba word-ngram TF-IDF with no external API.
- **Confidence from fallback depth**: Additive formula with `fallbacks` list for transparency.
- **bge-m3 embedding in hot path**: `vec_score` requires one embedding API call (via Ollama) per recommendation. This is the only API call in the hot path (state extraction is done by the caller).

## Files

| File | Purpose |
|------|---------|
| `src/f006_retrieval_engine/retrieval_engine.py` | Fact-set index, fallback cascade, recommend() |
| `src/tests/f006_retrieval_engine/test_retrieval_engine.py` | Unit tests for retrieval functions |
| `src/tests/f006_retrieval_engine/test_retrieval_ranking.py` | Unit tests for ranking functions |
