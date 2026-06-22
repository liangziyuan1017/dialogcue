---
id: F006
name: Retrieval & Ranking Engine
status: planned
owner: agent
source: plan_feature_base.md
created: 2026-06-22
updated: 2026-06-22
depends_on: F005
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
node_index: dict[tuple[tuple[str, ...], tuple[str, ...]], list[node]]
```

Key = `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)))`.

- `inherited_facts`: sorted alphabetically from the node's `inherited_facts` field
- `branch_key_values`: sorted alphabetically from the node's `branch_key` values (flattening lists: `{"facts": ["a", "b"]}` → `["a", "b"]`, `{"action": "closure"}` → `["closure"]`)

Both components are sorted independently, so any permutation of input keywords produces the same key. 267 unique keys → 315 nodes. 34 keys map to multiple nodes (aggregation cases).

### Retrieval Pipeline

1. **Key computation**: Sort `inherited_facts` alphabetically + sort `branch_key` values alphabetically → `(facts_tuple, bk_tuple)` — O(1)
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

### Dual Ranking Strategy

Two strategies switchable via `RANKING_STRATEGY`:

#### `limited` strategy (current 31-record dataset)

| Stage | Signal | Rationale |
|-------|--------|-----------|
| 1 | `bg_bitmask` AND | Hard filter — eliminate incompatible sentences |
| 2 | `conversation_context_similarity` DESC | With 1–3 samples per sentence, win_rate is mostly Laplace noise. Conversation context is the only reliable signal. |
| 3 | `win_rate` DESC | Proven effectiveness as secondary — weak signal at this scale |
| 4 | `sas` DESC | Tiebreak — intra-pool redundancy avoidance |

**Fallback when context unavailable**: Skip stage 2, promote win_rate to primary.

#### `full` strategy (10K+ records at scale)

| Stage | Signal | Rationale |
|-------|--------|-----------|
| 1 | `bg_bitmask` AND | Hard filter — eliminate incompatible sentences |
| 2 | `win_rate` DESC | Proven effectiveness is king — with 200+ samples, highly reliable |
| 3 | `conversation_context_similarity` DESC | Re-rank within clusters of similar win_rate |
| 4 | `bg_background` soft boost + `sas` DESC | Profile personalization + tiebreak |

**Fallback when context unavailable**: Skip stage 3 (win_rate already primary).

### Conversation Context Similarity

Each sentence has `source_call_ids` → look up original conversations, extract ~100 words before the sentence was used. Store as `conversation_context` field per sentence in the scored tree.

At retrieval time:
1. Compute TF-IDF char-bigram embedding of the current conversation's last ~100 words
2. Compute cosine similarity against each candidate sentence's stored `conversation_context` embedding
3. Use as ranking signal (position depends on strategy)

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

def recommend(inherited_facts, branch_key_values, query_bitmask, conversation_context, query_bg, strategy=RANKING_STRATEGY):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)))
    nodes = lookup_by_key(key, node_index)               # step 1-3
    pool = aggregate_pools(nodes)                         # step 4-6
    filtered = filter_by_bitmask(pool, query_bitmask)     # step 5-6
    if strategy == "limited":
        return _rank_limited(filtered, conversation_context)
    return _rank_full(filtered, conversation_context, query_bg)
```

### Output

```python
{
    "script_text": str,
    "script_id": str,
    "state_id": str,
    "win_rate": float,
    "sas": float,
    "conversation_context_similarity": float,
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
- `limited` strategy ranks conversation_context_similarity first, then win_rate
- `full` strategy ranks win_rate first, then conversation_context_similarity, then bg_background boost
- SAS is tiebreak in both strategies
- Confidence decreases with each fallback activated
- Retrieval latency < 50ms (hash lookup + filter + sort, no LLM in hot path)

## Acceptance Criteria

- [ ] `build_node_index()` creates index: 267 unique keys → 315 nodes
- [ ] Key is `(tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)))` — permutation-insensitive
- [ ] `lookup_by_key(key, index)` returns all nodes matching key — O(1)
- [ ] `aggregate_pools(nodes)` collects all sentences from all matched nodes
- [ ] `add_conversation_context()` extracts and stores ~100-word context per sentence
- [ ] `recommend(inherited_facts, branch_key_values, query_bitmask, conversation_context, query_bg, strategy)` returns top-1 script with all output fields
- [ ] Exact key match returns aggregated pool (confidence=1.0, fallbacks=[])
- [ ] Fallback 1: key drop finds broader key (fallbacks=["key_drop"])
- [ ] Fallback 2: empty pool descends to nearest descendants with sentences (fallbacks=["descend"])
- [ ] Fallback 2: descend includes ALL siblings at the same depth (e.g., "not married" + "married")
- [ ] Fallback 3: descend finds nothing → key drop retry (fallbacks=["descend", "key_drop"])
- [ ] Fallback 4: bitmask relaxation when all sentences eliminated (fallbacks=["bitmask_relax"])
- [ ] Fallback 5: missing conversation context adjusts ranking (fallbacks=["context_missing"])
- [ ] Fallback 6: completely empty tree returns None (confidence=0.0)
- [ ] Bitmask hard filter: incompatible sentences excluded
- [ ] `limited` strategy: context_similarity → win_rate → sas
- [ ] `full` strategy: win_rate → context_similarity → bg_background boost + sas
- [ ] `bg_background` soft boost computed correctly (industry +0.05, education +0.02, debt +0.03, age +0.02)
- [ ] `bg_background` boost not applied in `limited` strategy
- [ ] Confidence formula: 1.0 − (key_drops×0.1) − (descend_levels×0.05) − (bitmask_relax×0.05) − (context_missing×0.1), minimum 0.0
- [ ] No LLM call in hot path
- [ ] All 267 keys reachable via some (inherited_facts, branch_key_values) pair
- [ ] Conversation context cosine similarity computed via TF-IDF char-bigram
- [ ] Output file: `/src/retrieval_engine.py`

## Dependencies

- F005 (Context Tagging & Quality Scoring) — `decision_tree_scored.json` provides scored tree with bitmask + HWR + SAS + bg_background + inherited_facts

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F006 spec

## Implementation Plan

See [F006-implementation-plan.md](F006-implementation-plan.md)

## Design Decisions

- **Node index by (inherited_facts, branch_key_values)**: The lookup key combines `inherited_facts` and `branch_key` values, both sorted alphabetically. Sorting ensures permutation insensitivity: `["financial_hardship", "multiple_debts"]` and `["multiple_debts", "financial_hardship"]` produce the same key. 267 unique keys → 315 nodes. 34 keys map to multiple nodes (aggregation cases where the same conversational context appears at different tree positions).
- **Emotions and willingness NOT in key**: The tree uses facts and branch keys to identify conversational position. Emotions and willingness are branching dimensions within a key — they don't determine which node, they determine which sentences are available at that node.
- **Aggregate pool from matching nodes**: When a key matches multiple nodes, we pull sentences from ALL of them and rank across the combined pool. This gives the ranker more candidates and avoids premature filtering by tree position.
- **Descend fallback (not parent walk)**: When matched nodes have empty pools but have children, walk DOWN the tree (BFS) to find the nearest descendants with sentences. This is the correct direction — we've already matched the customer's facts, so the next scripts come from deeper in the tree (more specific actions/emotions), not from going back up. All siblings at the same depth are included: e.g., "unemployed" → "has kids" (empty) → {"not married", "married"} both contribute sentences.
- **Key-drop fallback after exhausted descend**: If descending finds no sentences at any depth (all descendants are routing-only nodes), then fall back to dropping a keyword from `inherited_facts` (least-frequent first) and retrying the lookup. This handles degenerate branches.
- **Bitmask relaxation, not removal**: When bitmask filter eliminates all sentences, relax one bit at a time (least significant first). Preserves the most important constraints while finding compatible sentences.
- **Bitmask AND as hard filter**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — eliminates objectively wrong recommendations regardless of ranking.
- **Dual strategy with switch**: `limited` (context-first) for sparse data; `full` (win_rate-first) for scaled data.
- **Context missing fallback**: `limited` mode promotes win_rate to primary; `full` mode no change.
- **bg_background as soft boost (full only)**: Shifts ranking toward profile-matching sentences without excluding viable ones. Excluded in limited mode due to sparsity.
- **SAS as tiebreak only**: Intra-pool similarity to highest-HWR sentence — redundancy avoidance, not relevance.
- **Confidence from fallback depth**: Additive formula with `fallbacks` list for transparency.
- **No LLM in hot path**: `recommend()` accepts pre-extracted facts, keeping hot path LLM-free and < 50ms.

## Files

| File | Purpose |
|------|---------|
| `src/retrieval_engine.py` | Fact-set index, fallback cascade, dual-strategy rank, recommend() |
| `src/test_retrieval_engine.py` | Unit tests for retrieval functions |
| `src/test_retrieval_engine_integration.py` | Integration tests on real scored tree |
