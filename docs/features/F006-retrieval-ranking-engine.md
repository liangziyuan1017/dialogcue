---
id: F006
name: Retrieval & Ranking Engine
status: complete
owner: agent
source: ROADMAP.md
created: 2026-06-22
updated: 2026-06-25
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
- **Conversation context**: last ~100 words from the customer-collector conversation
- **Database connection** (optional): `SentenceDB` instance for PostgreSQL-backed retrieval; falls back to in-memory JSON when `db=None`

### Architecture: Fact-Set Index → Pool Retrieval → Rank

The tree uses `inherited_facts` + `branch_key` values + `inherited_emotions` (all sorted alphabetically) as the node lookup key. Sorting ensures that permutations of keywords do not affect index matching. Multiple nodes sharing the same key represent the same conversational context at different tree positions — their sentences are aggregated into one candidate pool.

The retrieval engine:

1. **Matches by inherited_facts + branch_key** — emotions and willingness are NOT used to identify the node
2. **Retrieves sentences** from PostgreSQL (`db.get_sentences_by_node()`) when database provided, or aggregates from in-memory tree when `db=None`
3. **Ranks across the combined pool** using unified weighted fusion

### Node Index

Precompute at build time:

```
node_index: dict[tuple[tuple[str, ...], tuple[str, ...]], list[node]]
```

Key = `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))`.

- `inherited_facts`: sorted alphabetically from the node's `inherited_facts` field
- `branch_key_values`: sorted alphabetically from the node's `branch_key` values (flattening lists: `{"facts": ["a", "b"]}` → `["a", "b"]`, `{"action": "closure"}` → `["closure"]`)
- `inherited_emotions`: sorted alphabetically from the node's `inherited_emotions` field

All three components are sorted independently, so any permutation of input keywords produces the same key. 267 unique keys → 309 nodes. 34 keys map to multiple nodes (aggregation cases).

### Retrieval Pipeline

1. **Key computation**: Sort `inherited_facts` + sort `branch_key` values + sort `inherited_emotions` → `(facts_tuple, bk_tuple, emotions_tuple)` — O(1)
2. **Node lookup**: Hash map `key → list[node]` — O(1)
3. **Key fallback**: If exact key not in index, drop the least-frequent keyword from `inherited_facts` and retry — O(|facts|) worst case
4. **Pool retrieval**: `db.get_sentences_by_node(node_id)` when db provided, else `aggregate_pools(nodes)` from in-memory tree — O(nodes × pool_size)
5. **Descend fallback**: If pool is empty, walk DOWN the tree — collect sentences from the nearest descendants with non-empty pools (BFS). All siblings at the same depth are included.
6. **Key-drop fallback**: If descend fallback finds no sentences at any depth, drop the least-frequent keyword from `inherited_facts` and retry from step 1
7. **Hard filter**: Bitmask AND: `sentence.bg_bitmask_int & query_bitmask == sentence.bg_bitmask_int`
8. **Filter fallback**: If bitmask eliminates ALL sentences, relax constraints progressively
9. **Rank** (unified weighted fusion, see below)
10. **Return**: Top-1 script

### Fallback Cascade

| # | Failure point | Cause | Fallback | Confidence impact |
|---|--------------|-------|----------|-------------------|
| 1 | **Key miss** | `(sorted_facts, sorted_bk)` not in `node_index` | Drop least-frequent keyword from `inherited_facts`, recompute key, retry. Repeat until match or empty facts. | Each drop: −0.1 |
| 2 | **Empty pool — descend** | All matched nodes have empty `sentence_pool` but have children | Walk DOWN tree (BFS): collect sentences from nearest descendants with non-empty pools. All siblings at the same depth are included. | Each level: −0.05 |
| 3 | **Empty pool — key drop** | Descend found no sentences at any depth | Drop least-frequent keyword from `inherited_facts`, retry from key lookup. | Each drop: −0.1 |
| 4 | **Bitmask eliminates all** | No sentence passes `(sb & qb) == sb` | Clear lowest set bit in query bitmask, retry. Continue until match or bitmask=0. | Each bit: −0.05 |
| 5 | **Context missing** | No conversation context provided (first turn) | Set `vec_score = 0`, redistribute weight to `win_rate`. | −0.1 |
| 5b | **Embed fail** | LLM embedding API fails | Set `vec_score = 0`, rank by `win_rate` + `sas` only. | −0.1 |
| 6 | **No sentences at all** | No sentences found at any depth, even at root | Return `None` with confidence 0.0. | 0.0 |

**Descend fallback detail**: BFS from matched nodes' children. At each depth level, check all nodes at that level. If any have non-empty pools, collect from all of them (siblings at the same depth are equally valid next steps). If all are empty, descend one more level.

**Confidence formula**:
```
confidence = 1.0
           − (fact_drops × 0.1)
           − (descend_levels × 0.05)
           − (bitmask_relaxations × 0.05)
           − (context_missing × 0.1)
           − (embed_fail × 0.1)
```
Minimum: 0.0.

### Unified Weighted Fusion Ranking

Replaces the previous dual-strategy (`limited`/`full`) with a single weighted fusion:

```
final_score = 0.40 × win_rate + 0.30 × vec_score + 0.15 × sas + 0.15 × bg_boost
```

| Signal | Weight | Source | Rationale |
|--------|--------|--------|-----------|
| `win_rate` | 0.40 | Blended HWR (F005) | Proven effectiveness is the strongest signal |
| `vec_score` | 0.30 | Vector cosine similarity (bge-m3 via Ollama, F007b) | Semantic relevance of current conversation to historical scripts |
| `sas` | 0.15 | Char-ngram TF-IDF cosine similarity (F005) | Intra-node redundancy avoidance (tiebreak) |
| `bg_boost` | 0.15 | Profile match boost | Customer profile personalization |

**Fallback when embedding unavailable**: Set `vec_score = 0`, redistribute weight to `win_rate`.

**bg_boost computation**:

| Match condition | Boost |
|----------------|-------|
| Exact industry match | +0.05 |
| Same education bracket | +0.02 |
| Similar debt range (within 50%) | +0.03 |
| Age within 10 years | +0.02 |

### Switch

```python
RANKING_WEIGHTS = {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15}

def recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg, db=None):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
    nodes = lookup_by_key(key, node_index)               # step 1-3
    pool = db.get_sentences_by_node(node_id) if db else aggregate_pools(nodes)  # step 4-6
    filtered = filter_by_bitmask(pool, query_bitmask)     # step 7-8
    return rank_sentences(filtered, query_vec, db, query_bg, conversation_context)
```

### Output

```python
{
    "script_text": str,
    "script_id": str,
    "state_id": str,
    "win_rate": float,
    "sas": float,
    "vec_score": float,
    "final_score": float,
    "confidence": float,
    "ranking_weights": dict,
    "fallbacks": [str],
    "conversation_state": dict,
}
```

## Passing Criteria

- `recommend()` returns all fields in the output schema
- Fact set match returns aggregated pool from all sibling nodes
- Fallback (fact drop) returns pool from broader fact set
- Bitmask filtering excludes sentences with incompatible bitmask (hard filter)
- Unified fusion ranking: `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`
- Confidence decreases with each fallback activated
- Retrieval latency < 50ms (hash lookup + filter + sort, no LLM in hot path)

## Acceptance Criteria

- [x] `build_node_index()` creates index: 267 unique keys → 309 nodes
- [x] Key is `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))` — permutation-insensitive
- [x] `lookup_by_key(key, index)` returns all nodes matching key — O(1)
- [x] `aggregate_pools(nodes)` collects all sentences from all matched nodes
- [x] `add_conversation_context()` extracts and stores ~100-word context per sentence
- [x] `recommend(inherited_facts, branch_key_values, query_bitmask, conversation_context, query_bg, db)` returns top-1 script with all output fields
- [x] Exact key match returns aggregated pool (confidence=1.0, fallbacks=[])
- [x] Fallback 1: key drop finds broader key (fallbacks=["key_drop"])
- [x] Fallback 2: empty pool descends to nearest descendants with sentences (fallbacks=["descend"])
- [x] Fallback 2: descend includes ALL siblings at the same depth (e.g., "not married" + "married")
- [x] Fallback 3: descend finds nothing → key drop retry (fallbacks=["descend", "key_drop"])
- [x] Fallback 4: bitmask relaxation when all sentences eliminated (fallbacks=["bitmask_relax"])
- [x] Fallback 5: missing conversation context adjusts ranking (fallbacks=["context_missing"])
- [x] Fallback 6: completely empty tree returns None (confidence=0.0)
- [x] Bitmask hard filter: incompatible sentences excluded
- [x] Unified fusion ranking: `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`
- [x] `bg_background` soft boost computed correctly (industry +0.05, education +0.02, debt +0.03, age +0.02)
- [x] `vec_score` computed via bge-m3 vector cosine similarity (F007b/ADR-024)
- [x] `db` parameter: when provided, candidates from PostgreSQL; when None, in-memory aggregate_pools
- [x] Confidence formula: 1.0 − (key_drops×0.1) − (descend_levels×0.05) − (bitmask_relax×0.05) − (context_missing×0.1), minimum 0.0
- [x] No LLM call in hot path
- [x] All 267 keys reachable via some (inherited_facts, branch_key_values, inherited_emotions) pair
- [x] Output file: `/src/f006_retrieval_engine/retrieval_engine.py`

## Dependencies

- F005 (Context Tagging & Quality Scoring) — `decision_tree_scored.json` provides scored tree with bitmask + HWR + SAS + bg_background + inherited_facts
- F007 (Infrastructure Layer) — PostgreSQL + pgvector for vector-backed retrieval (optional)
- F007b (Vector Retrieval Integration) — `compute_vec_similarity()` and `RANKING_WEIGHTS` for unified fusion

## Links

- [ROADMAP.md](../ROADMAP.md) — dependency graph + architecture decisions
- [ADR-024](../decisions/ADR-024-embedding-architecture.md) — Embedding architecture (bge-m3 via Ollama)

## Implementation Plan

See [implementation-plan.md](F006-implementation-plan.md)

## Design Decisions

- **Node index by (inherited_facts, branch_key_values, inherited_emotions)**: The lookup key combines `inherited_facts`, `branch_key` values, and `inherited_emotions`, all sorted alphabetically. Sorting ensures permutation insensitivity. 267 unique keys → 309 nodes. 34 keys map to multiple nodes (aggregation cases).
- **Emotions ARE in the key**: Without `inherited_emotions`, 31 key collisions occur (e.g., `a:closure` under `['disappointment']` vs `['anger']` must not aggregate). Willingness is tracked in conversation state but NOT in the node key.
- **PostgreSQL-backed retrieval when db provided**: `recommend()` accepts optional `db` parameter. When provided, uses `db.get_sentences_by_node()` for candidate retrieval. Falls back to in-memory `aggregate_pools()` when `db=None` (backward compat for offline use).
- **Descend fallback (not parent walk)**: When matched nodes have empty pools but have children, walk DOWN the tree (BFS) to find the nearest descendants with sentences. All siblings at the same depth are included.
- **Key-drop fallback after exhausted descend**: If descending finds no sentences at any depth, fall back to dropping a keyword from `inherited_facts` (least-frequent first) and retrying.
- **Bitmask relaxation, not removal**: When bitmask filter eliminates all sentences, relax one bit at a time (least significant first).
- **Bitmask AND as hard filter**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — eliminates objectively wrong recommendations regardless of ranking.
- **Unified weighted fusion (replaces dual strategy)**: Single ranking formula `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`. The dual-strategy switch (`limited`/`full`) was removed in F007b because vector similarity provides a meaningful semantic signal at any data scale, making the strategy switch unnecessary.
- **bg_background as soft boost**: Shifts ranking toward profile-matching sentences without excluding viable ones.
- **SAS as secondary signal (weight 0.15)**: Intra-pool similarity to highest-HWR sentence — redundancy avoidance. Primary semantic signal is now `vec_score` (weight 0.30) via bge-m3 embeddings.
- **Confidence from fallback depth**: Additive formula with `fallbacks` list for transparency.
- **No LLM in hot path**: `recommend()` accepts pre-extracted facts, keeping hot path LLM-free and < 50ms.

## Files

| File | Purpose |
|------|---------|
| `src/f006_retrieval_engine/retrieval_engine.py` | Fact-set index, fallback cascade, recommend() |
| `src/f006_retrieval_engine/retrieval_ranking.py` | Unified weighted fusion ranking, compute_vec_similarity, compute_bg_boost |
| `src/f008_state_extraction/state_extraction.py` | LLM-first + keyword fallback state extraction (F008) |
| `src/tests/f006_retrieval_engine/test_retrieval_engine.py` | Unit tests for retrieval functions |
| `src/tests/f006_retrieval_engine/test_retrieval_ranking.py` | Unit tests for ranking functions |
| `src/tests/f006_retrieval_engine/test_retrieval_engine_integration.py` | Integration tests on real scored tree |
