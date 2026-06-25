---
id: F006
name: Retrieval & Ranking Engine
status: complete
owner: agent
source: plan_feature_base.md
created: 2026-06-22
updated: 2026-06-22
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

### Architecture: Fact-Set Index → Aggregate Pool → Rank

The tree uses `inherited_facts` + `branch_key` values (both sorted alphabetically) as the node lookup key. Sorting ensures that permutations of keywords do not affect index matching. Multiple nodes sharing the same key represent the same conversational context at different tree positions — their sentences are aggregated into one candidate pool.

The retrieval engine:

1. **Matches by inherited_facts + branch_key** — emotions and willingness are NOT used to identify the node
2. **Aggregates all sentences** from all nodes sharing the same key into a single candidate pool
3. **Ranks across the combined pool** using the dual-strategy ranker

### Node Index

Precompute at build time:

```
node_index: dict[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], list[node]]
```

Key = `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))`.

- `inherited_facts`: sorted alphabetically from the node's `inherited_facts` field
- `branch_key_values`: sorted alphabetically from the node's `branch_key` values (flattening lists: `{"facts": ["a", "b"]}` → `["a", "b"]`, `{"action": "closure"}` → `["closure"]`)
- `inherited_emotions`: sorted alphabetically from the node's `inherited_emotions` field

All three components are sorted independently, so any permutation of input keywords produces the same key. `inherited_emotions` is required: without it, 31 key collisions occur (e.g., `a:closure` under `['disappointment']` vs `['anger']` must not aggregate). The tree's own dedup identity (`tree_transforms.py:_make_identity`) already uses all three components. Willingness is tracked in conversation state but **not** in the node key.

### Retrieval Pipeline

1. **Key computation**: Sort `inherited_facts` alphabetically + sort `branch_key` values alphabetically + sort `inherited_emotions` alphabetically → `(facts_tuple, bk_tuple, emotions_tuple)` — O(1)
2. **Node lookup**: Hash map `key → list[node]` — O(1)
3. **Key fallback**: If exact key not in index, drop the least-frequent keyword from `inherited_facts` and retry — O(|facts|) worst case
4. **Pool aggregation**: Collect `sentence_pool` from all matched nodes — O(nodes × pool_size)
5. **Descend fallback**: If aggregated pool is empty, walk DOWN the tree — collect sentences from the nearest descendants with non-empty pools (BFS). All siblings at the same depth are included. E.g., if "unemployed" has no sentences, and its child "has kids" also has none, but "has kids" branches into "not married" and "married" which both have sentences → collect from both grandchildren.
6. **Key-drop fallback**: If descend fallback finds no sentences at any depth, drop the least-frequent keyword from `inherited_facts` and retry from step 1
6. **Hard filter**: Bitmask AND: `sentence.bg_bitmask_int & query_bitmask == sentence.bg_bitmask_int`
7. **Filter fallback**: If bitmask eliminates ALL sentences, relax constraints progressively
8. **Rank** (dual strategy, see below)
9. **Return**: Top-1 script

### Fallback Cascade

| # | Failure point | Cause | Fallback | Confidence impact |
|---|--------------|-------|----------|-------------------|
| 1 | **Key miss** | `(sorted_facts, sorted_bk)` not in `node_index` | Drop least-frequent keyword from `inherited_facts`, recompute key, retry. Repeat until match or empty facts. | Each drop: −0.1 |
| 2 | **Empty pool — descend** | All matched nodes have empty `sentence_pool` but have children | Walk DOWN tree (BFS): collect sentences from nearest descendants with non-empty pools. All siblings at the same depth are included. E.g., "unemployed" → "has kids" (empty) → {"not married", "married"} (both have sentences) → collect from both. | Each level: −0.05 |
| 3 | **Empty pool — key drop** | Descend found no sentences at any depth | Drop least-frequent keyword from `inherited_facts`, retry from key lookup. | Each drop: −0.1 |
| 4 | **Bitmask eliminates all** | No sentence passes `(sb & qb) == sb` | Clear lowest set bit in query bitmask, retry. Continue until match or bitmask=0. | Each bit: −0.05 |
| 5 | **Context missing** | No conversation context provided (first turn) | Skip context similarity ranking. `limited`: promote win_rate to primary. `full`: no change. | −0.1 |
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
    "win_rate": 0.40,
    "vec_score": 0.30,
    "sas": 0.15,
    "bg_boost": 0.15,
}
```

`final_score = 0.40 × win_rate + 0.30 × vec_score + 0.15 × sas + 0.15 × bg_boost`

**Strategy switch** (`limited` vs `full`) controls only `bg_boost` applicability:
- `limited`: `bg_boost = 0.0` (too sparse for profile matching at 31 records)
- `full`: `bg_boost` computed from profile similarity

**Fallback when embedding unavailable**: Set `vec_score = 0`, redistribute weight to `win_rate`. −0.1 confidence.

### Conversation Context Similarity (pgvector)

Each sentence has `source_call_ids` → look up original conversations, extract ~100 words before the sentence was used. Store as `conversation_context` field per sentence in the scored tree. At F005 build time, compute `embed(conversation_context)` via DeepSeek embedding API → 768-dim vector stored in PostgreSQL `embedding` column with pgvector HNSW index.

At retrieval time:
1. Compute `embed(query_context)` via DeepSeek embedding API for the current conversation's last ~100 words
2. Compute `vec_score = 1 - (embedding <=> query_vec)` via pgvector cosine similarity
3. Use as ranking signal in weighted fusion

### bg_background Soft Boost (full strategy only)

| Match condition | Boost |
|----------------|-------|
| Exact industry match | +0.05 |
| Same education bracket | +0.02 |
| Similar debt range (within 50%) | +0.03 |
| Age within 10 years | +0.02 |

### Switch

```python
RANKING_STRATEGY = "limited"  # or "full"

def recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg, strategy=RANKING_STRATEGY):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
    nodes = lookup_by_key(key, node_index)               # step 1-3
    pool = aggregate_pools(nodes)                         # step 4-6
    filtered = filter_by_bitmask(pool, query_bitmask)     # step 5-6
    vec_score = compute_vec_score(filtered, conversation_context)  # pgvector
    bg_boost = compute_bg_boost(...) if strategy == "full" else 0.0
    final_score = 0.40 * win_rate + 0.30 * vec_score + 0.15 * sas + 0.15 * bg_boost
    return top_by_final_score(filtered)
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
- Bitmask filtering excludes sentences with incompatible bitmask (hard filter)
- Weighted fusion: `final_score = 0.40 × win_rate + 0.30 × vec_score + 0.15 × sas + 0.15 × bg_boost`
- `limited` strategy: bg_boost = 0.0
- `full` strategy: bg_boost computed from profile similarity
- Confidence decreases with each fallback activated
- Retrieval latency < 150ms (hash lookup + embed API + filter + sort)

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
- [ ] Bitmask hard filter: incompatible sentences excluded
- [ ] Weighted fusion: `final_score = 0.40 * win_rate + 0.30 * vec_score + 0.15 * sas + 0.15 * bg_boost`
- [ ] `limited` strategy: bg_boost = 0.0
- [ ] `full` strategy: bg_boost computed from profile similarity
- [ ] `vec_score` computed via pgvector cosine similarity
- [ ] `bg_background` soft boost computed correctly (industry +0.05, education +0.02, debt +0.03, age +0.02)
- [ ] `bg_background` boost not applied in `limited` strategy
- [ ] Confidence formula: 1.0 − (key_drops×0.1) − (descend_levels×0.05) − (bitmask_relax×0.05) − (context_missing×0.1), minimum 0.0
- [ ] No LLM call for state extraction in hot path (state is pre-extracted by caller)
- [ ] DeepSeek embedding API call for `vec_score` is the only API in hot path
- [ ] All keys reachable via some (inherited_facts, branch_key_values, inherited_emotions) pair
- [ ] Conversation context cosine similarity computed via pgvector on DeepSeek embeddings
- [ ] Output file: `/src/f006_retrieval_engine/retrieval_engine.py`

## Dependencies

- F005 (Context Tagging & Quality Scoring) — `decision_tree_scored.json` provides scored tree with bitmask + HWR + SAS + bg_background + inherited_facts

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F006 spec

## Implementation Plan

See [implementation-plan.md](implementation-plan.md)

## Design Decisions

- **Node index by (inherited_facts, branch_key_values, inherited_emotions)**: The lookup key combines `inherited_facts`, `branch_key` values, and `inherited_emotions`, all sorted alphabetically. Sorting ensures permutation insensitivity. `inherited_emotions` is required: without it, 31 key collisions occur (e.g., `a:closure` under `['disappointment']` vs `['anger']` must not aggregate). The tree's own dedup identity (`tree_transforms.py:_make_identity`) already uses all three components.
- **Willingness not in key**: Willingness is a scalar (not a list) and represents the customer's current repayment intent. It's tracked in conversation state but doesn't determine node identity — it's a soft signal, not a branching dimension.
- **Aggregate pool from matching nodes**: When a key matches multiple nodes, we pull sentences from ALL of them and rank across the combined pool. This gives the ranker more candidates and avoids premature filtering by tree position.
- **Descend fallback (not parent walk)**: When matched nodes have empty pools but have children, walk DOWN the tree (BFS) to find the nearest descendants with sentences. This is the correct direction — we've already matched the customer's facts, so the next scripts come from deeper in the tree (more specific actions/emotions), not from going back up. All siblings at the same depth are included: e.g., "unemployed" → "has kids" (empty) → {"not married", "married"} both contribute sentences.
- **Key-drop fallback after exhausted descend**: If descending finds no sentences at any depth (all descendants are routing-only nodes), then fall back to dropping a keyword from `inherited_facts` (least-frequent first) and retrying the lookup. This handles degenerate branches.
- **Bitmask relaxation, not removal**: When bitmask filter eliminates all sentences, relax one bit at a time (least significant first). Preserves the most important constraints while finding compatible sentences.
- **Bitmask AND as hard filter**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — eliminates objectively wrong recommendations regardless of ranking.
- **Weighted fusion ranking**: `final_score = 0.40 × win_rate + 0.30 × vec_score + 0.15 × sas + 0.15 × bg_boost`. All four signals contribute simultaneously rather than staged sorting. `vec_score` from pgvector captures cross-conversation semantic similarity. Strategy switch (`limited`/`full`) controls only `bg_boost` applicability.
- **Context missing fallback**: Set `vec_score = 0`, redistribute weight to `win_rate`. −0.1 confidence.
- **bg_background as soft boost (full only)**: Shifts ranking toward profile-matching sentences without excluding viable ones. Excluded in limited mode due to sparsity.
- **SAS as intra-pool diversity**: Intra-pool similarity to highest-HWR sentence — redundancy avoidance, not relevance. Uses TF-IDF char-bigram (no API).
- **Confidence from fallback depth**: Additive formula with `fallbacks` list for transparency.
- **DeepSeek embedding in hot path**: `vec_score` requires one embedding API call per recommendation. This is the only API call in the hot path (state extraction is done by the caller).

## Files

| File | Purpose |
|------|---------|
| `src/f006_retrieval_engine/retrieval_engine.py` | Fact-set index, fallback cascade, dual-strategy rank, recommend() |
| `src/test_retrieval_engine.py` | Unit tests for retrieval functions |
| `src/test_retrieval_engine_integration.py` | Integration tests on real scored tree |
