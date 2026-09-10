# F006 Implementation Plan

## Step 1: Build Node Index

Precompute `node_index` from the scored tree.

- Walk tree, for each node compute:
  - `facts_key = tuple(sorted(node["inherited_facts"]))`
  - `bk_vals = []`; for each (k, v) in `branch_key`: if v is list, extend; else append
  - `bk_key = tuple(sorted(bk_vals))`
  - `key = (facts_key, bk_key)`
- Group nodes by key: `node_index[key] = [node, ...]`
- 267 unique keys → 315 nodes

TDD:
1. Write test: `build_node_index` has 267 unique keys
2. Write test: total nodes across all values = 315
3. Write test: root key = `((), ())` maps to 1 node
4. Write test: key `((), ("closure",))` maps to 2 nodes (aggregation)
5. Write test: permutation insensitivity — same facts/bk in different order produce same key
6. Implement `build_node_index(tree)`

## Step 2: Lookup by Key

Given `inherited_facts` (list) + `branch_key_values` (list), sort both and lookup.

TDD:
1. Write test: `lookup_by_key(["financial_hardship"], ["empathy"], index)` returns matching nodes
2. Write test: `lookup_by_key([], [], index)` returns root node
3. Write test: facts/bk in different order produce same REMOVED_FIELD_result (permutation insensitivity)
4. Write test: unknown key returns empty list
5. Implement `lookup_by_key(inherited_facts, branch_key_values, index)`

## Step 3: Aggregate Pools

Collect all sentences from all matched nodes into one pool.

TDD:
1. Write test: single node with 3 sentences → pool of 3
2. Write test: 7 nodes each with 1 sentence → pool of 7
3. Write test: nodes with empty pools contribute nothing
4. Write test: all pools empty → empty REMOVED_FIELD_result
5. Implement `aggregate_pools(nodes)`

## Step 4: Fallback 1 — Key Drop

If key not in index, drop least-frequent keyword from `inherited_facts` and retry.

- Compute keyword frequency across all keys in the index
- Drop the least-frequent keyword from `inherited_facts`, re-sort, retry lookup
- Each drop: confidence −0.1, record "key_drop" in fallbacks
- Continue until match or empty `inherited_facts`

TDD:
1. Write test: exact match returns nodes (confidence=1.0, fallbacks=[])
2. Write test: miss with 1 drop returns broader key (fallbacks=["key_drop"])
3. Write test: miss with 2 drops (fallbacks=["key_drop", "key_drop"])
4. Write test: drops least-frequent keyword first
5. Write test: all keywords dropped → root-level lookup
6. Implement `lookup_with_fallback(inherited_facts, branch_key_values, index, keyword_freq)`

## Step 5: Fallback 2 — Descend for Sentences

Matched nodes have empty sentence_pools. Walk DOWN the tree (BFS) to find nearest descendants with sentences.

- BFS from matched nodes' children
- At each depth, check all nodes: if any have non-empty pools, collect from ALL of them (siblings at same depth)
- If all empty at this depth, descend one more level
- Each level: confidence −0.05, record "descend" in fallbacks
- If no sentences found at any depth, trigger fact-drop fallback

TDD:
1. Write test: non-empty pool returns as-is (no fallback)
2. Write test: empty pool, children have sentences → collect from children (fallbacks=["descend"])
3. Write test: empty pool, children also empty, grandchildren have sentences → collect from grandchildren (fallbacks=["descend", "descend"])
4. Write test: multiple siblings at same depth all contribute (e.g., "not married" + "married")
5. Write test: no sentences at any depth → trigger key drop (fallbacks=["descend", "key_drop"])
6. Implement `descend_for_sentences(nodes)`

## Step 6: Bitmask Hard Filter + Fallback 3

Filter by bitmask compatibility. If all eliminated, relax constraints.

- Hard filter: `(sentence.bg_bitmask_int & query_bitmask) == sentence.bg_bitmask_int`
- If empty, clear lowest set bit in query_bitmask, retry
- Each relaxation: confidence −0.05, record "bitmask_relax"

TDD:
1. Write test: sentence with bitmask 0 passes all queries
2. Write test: incompatible sentence excluded
3. Write test: all eliminated → 1-bit relaxation (fallbacks=["bitmask_relax"])
4. Write test: multiple relaxations recorded
5. Write test: all bits relaxed → all sentences pass
6. Implement `filter_by_bitmask(pool, query_bitmask)` and `relax_bitmask(pool, query_bitmask)`

## Step 7: Conversation Context + Fallback 4

- If context missing: skip vector scoring, record "context_missing"
- Set `vec_score = 0`, redistribute weight to `win_rate`

TDD:
1. Write test: `add_conversation_context()` stores `conversation_context` on each sentence
2. Write test: missing context triggers fallback (fallbacks=["context_missing"])
3. Write test: missing context sets vec_score = 0
4. Implement `add_conversation_context()`

## Step 8: bg_background Soft Boost

Compute light similarity score.

- Industry match: +0.05, education: +0.02, debt range ±50%: +0.03, age ±10yr: +0.02

TDD:
1. Write test: matching industry adds 0.05
2. Write test: no match returns 0.0
3. Write test: all matches sum correctly
4. Implement `compute_bg_boost(sentence_bg, query_bg)`

## Step 9: Unified Weighted Fusion Ranking

Single ranking formula: `final_score = 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`

TDD:
1. Write test: `RANKING_WEIGHTS` dict has correct keys and sums to 1.0
2. Write test: `rank_sentences()` computes correct `final_score`
3. Write test: sorted by `final_score` DESC
4. Write test: bitmask filter applied first
5. Write test: bg_background boost applied
6. Write test: SAS is secondary signal
7. Write test: empty pool returns empty list
8. Implement `rank_sentences()` with unified fusion

## Step 10: recommend() Integration

Wire steps 1–9 into `recommend(facts, query_bitmask, conversation_context, query_bg, db=None)`.

TDD:
1. Write test: exact match → top-1 with all fields (confidence=1.0, fallbacks=[])
2. Write test: key drop fallback (fallbacks=["key_drop"])
3. Write test: descend fallback (fallbacks=["descend"])
4. Write test: descend with multiple siblings at same depth
5. Write test: descend exhausted → key drop (fallbacks=["descend", "key_drop"])
6. Write test: bitmask relaxation fallback (fallbacks=["bitmask_relax"])
7. Write test: context missing fallback (fallbacks=["context_missing"])
8. Write test: cascading fallbacks in order
9. Write test: confidence formula
10. Write test: terminal case returns None (confidence=0.0)
11. Write test: db parameter uses PostgreSQL when provided, in-memory when None
12. Implement `recommend()`

## Step 11: Integration Tests on Real Tree

1. Load `decision_tree_scored.json`, build node index
2. Test: all 267 keys reachable
3. Test: recommend with known key returns expected script
4. Test: recommend with incompatible bitmask triggers relaxation
5. Test: unified fusion ranking produces correct final_score
6. Test: conversation context similarity computed correctly
7. Test: descend fallback on empty-pool nodes with children
8. Test: descend includes all siblings at same depth
9. Test: retrieval latency < 50ms

## Config Externalization (F011)

All ranking weights, boost values, confidence penalties, and pool cap are now configurable via `config.md`:

| Parameter | config.md key | Default |
|-----------|--------------|---------|
| win_rate weight | `ranking_weights.win_rate` | 0.40 |
| vec_score weight | `ranking_weights.vec_score` | 0.30 |
| sas weight | `ranking_weights.sas` | 0.15 |
| bg_boost weight | `ranking_weights.bg_boost` | 0.15 |
| industry boost | `bg_boost.industry_match` | 0.05 |
| education boost | `bg_boost.education_match` | 0.02 |
| debt+interest boost | `bg_boost.debt_interest_match` | 0.03 |
| age proximity boost | `bg_boost.age_proximity_match` | 0.02 |
| age threshold | `bg_boost.age_proximity_threshold` | 10 |
| pool cap | `pool_cap` | 50 |
| subset drop penalty | `confidence.subset_drop_penalty` | 0.1 |
| root fallback | `confidence.root_fallback` | 0.2 |
| descend penalty | `confidence.descend_penalty` | 0.05 |
| context missing penalty | `confidence.context_missing_penalty` | 0.1 |
| bitmask relax penalty | `confidence.bitmask_relax_penalty` | 0.05 |

---

## Update Log

**2026-07-10 — Ranking weights updated (5-signal):** The 4-signal formula `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost` shown in Step 9 and the Config Externalization table above was the original design. The current codebase uses a 5-signal formula with `bitmask_score` added: `0.35*win_rate + 0.25*vec_score + 0.10*sas + 0.10*bg_boost + 0.20*bitmask_score`. Weights are configurable in `config.md` under `ranking_weights`. Current defaults: `win_rate=0.35, vec_score=0.25, sas=0.10, bg_boost=0.10, bitmask_score=0.20`.
