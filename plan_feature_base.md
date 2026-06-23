# Feature-Wise Implementation Plan: Debt Collection Script Recommendation System

## Overview

Decompose the phase-based plan into independently developable features. Each feature states its goal, passing criteria, and dependencies. All new code lives under `/src`. Data input is `/data/output_manual.py`.

---

## Dependency Graph

```
F000 ──► F001 ──► F003 ──► F004 ──► F005 ──► F006
                                    │
                             F007 ──┘
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

**Status:** Removed per ADR-009. F001's manual annotations (493/805 turns) are sufficient. Downstream features handle missing `state` on unlabeled turns.

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

## F005: Context Tagging & Quality Scoring

**Depends on:** F004

**Goal:** Tag each sentence with `bg_constraints` from source conversation's customer profile, encode as bitmask for O(1) filtering. Compute HWR (node-level aggregation with sentence-level blending) and SAS (TF-IDF cosine similarity). UC and CSI deferred. Output to `/src/decision_tree_scored.json`.

**Passing criteria:**
- Every sentence has `bg_constraints` dict with all 5 bitmask fields
- Every sentence has `bg_bitmask` integer
- Every sentence has `win_rate` (blended HWR) ≥ 0
- Every sentence has `win_rate_node` (node-level HWR) ≥ 0
- Every sentence has `sas` ≥ 0
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset

---

## F006: Retrieval & Ranking Engine

**Depends on:** F005

**Goal:** Build `recommend()` function — given real-time customer utterance + context, extract state via LLM, compute path signature from state, look up node via hash index (O(1)), hard-filter sentences by bitmask, rank by HWR (primary) + SAS (secondary), return top-1 script. Output to `/src/f006_retrieval_engine/retrieval_engine.py`.

**Architecture:** No graph traversal at retrieval time. The decision tree is a **key-value lookup problem**: each node's position is fully determined by its path signature (e.g., `f:financial_hardship|e:pleading|a:pressure`). Precompute `path_signature` for every node at build time. At retrieval time, compute the signature from the customer state and do a single hash lookup. This is O(1) regardless of tree size.

**Retrieval pipeline:**
1. **State extraction**: LLM extracts facts + emotions from customer utterance → state vector
2. **Path computation**: Derive path signature from state (deterministic, no tree walk)
3. **Node lookup**: Hash map `signature → node` — O(1)
4. **Fallback**: If exact signature miss, strip tags progressively (same as current `_strip_key`) and retry — O(depth) worst case
5. **Sentence retrieval**: Get node's `sentence_pool` — O(1) pointer
6. **Context filter**: Bitmask AND: `sentence.bg_bitmask_int & query_bitmask == sentence.bg_bitmask_int` — O(pool_size), typically <20
7. **Rank**: Sort by `win_rate` desc, `sas` desc — O(pool_size log pool_size)
8. **Return**: Top-1 script

**Why not Neo4j:** This is a tree with deterministic paths, not a graph with arbitrary relationships. Queries are point lookups by path signature, not traversals. Neo4j's property graph model and ACID overhead add latency without benefit. SQLite (or in-memory hash map) gives O(1) lookup with far less overhead.

**Passing criteria:**
- `recommend()` returns `{ script_text, state_id, win_rate, confidence }`
- Exact state match returns sentence from matched node's pool via hash lookup
- Fallback (tag removal) returns sentence from sub-state node
- Context filtering excludes sentences with incompatible bitmask
- Ranking prefers higher HWR; SAS breaks ties
- Retrieval latency < 50ms (hash lookup + filter + sort, no LLM in hot path)

---

## F007: Scaling Architecture Design

**Depends on:** F005

**Goal:** Document migration path from 31 → 100,000+ nodes. The key insight: retrieval is O(1) hash lookup regardless of tree size (F006 architecture). Scaling challenges are storage, build-time, and index maintenance — not retrieval latency.

**Scaling dimensions:**

| Dimension | Current (31 records) | Target (10K+ records) | Solution |
|-----------|---------------------|----------------------|----------|
| Nodes | 315 | 100,000+ | Tree grows with record diversity, not linearly with records |
| Storage | JSON file (2MB) | SQLite with indexed `path_signature` column | O(1) lookup via covering index |
| Build time | ~30s (with LLM merge) | Batch LLM + incremental rebuild | Only rebuild affected subtrees on new data |
| Child lookup | Linear scan of `children[]` | Hash map `branch_key → child` per node | O(1) child resolution |
| Sentence pool | In-memory array | SQLite `sentences` table with `node_id` FK | Filter + rank via SQL with bitmask index |
| Context filter | Python loop | SQLite bitwise op: `bg_bitmask_int & ? == bg_bitmask_int` | Indexed with expression index |
| Retrieval | JSON load + tree walk | Hash lookup or SQL `SELECT ... WHERE path_signature = ?` | O(1) or O(log N) with B-tree |

**Architecture at scale:**

```
Build time:
  records → merge_collector_turns → build_tree → score_tree → SQLite

Storage (SQLite):
  nodes(id, path_signature, branch_key, parent_id, depth, type)
  sentences(id, node_id, script_text, bg_bitmask_int, win_rate, sas, ...)
  Index: nodes.path_signature UNIQUE
  Index: sentences.node_id
  Index: sentences.bg_bitmask_int  (for bitmask filter)

Retrieval (hot path, no LLM):
  state → path_signature → SELECT from nodes WHERE path_signature = ?
         → SELECT from sentences WHERE node_id = ? AND (bg_bitmask_int & ?) = bg_bitmask_int
         → ORDER BY win_rate DESC, sas DESC LIMIT 1
```

**Migration steps:**

1. **JSON → SQLite**: Write `build_tree` output to SQLite instead of JSON. Add `path_signature` column. Same retrieval logic, different storage.
2. **Hash index for child lookup**: Replace `children[]` linear scan with `dict[branch_key] → child` per node. O(1) child resolution during tree build and retrieval.
3. **Incremental rebuild**: On new records, only rebuild affected subtrees (identified by changed branch keys). Cache unchanged subtrees.
4. **Batch LLM merge**: Process merge candidates in batches (current: sequential). Use merge cache to avoid re-calling LLM for unchanged groups.
5. **Expression index for bitmask**: SQLite `CREATE INDEX ... ON sentences(bg_bitmask_int & <query>)` for fast context filtering at scale.

**Why SQLite over PostgreSQL/Milvus/Neo4j:**
- **PostgreSQL**: Overkill for single-table lookups. SQLite is serverless, embedded, and faster for point queries.
- **Milvus/pgvector**: Vector search is only needed for soft/fallback matching (Step 4 of retrieval), not the primary path. Add later if needed.
- **Neo4j**: This is a tree, not a graph. No cycles, no arbitrary edges, no multi-hop traversals. Neo4j's overhead (property graph, ACID, Bolt protocol) adds latency without benefit.

**Commercial & open-source options for later discussion:**

### Hot Path — O(1) Node Lookup

| Option | Latency | Notes |
|--------|---------|-------|
| **Redis / Valkey** | <1ms | In-memory hash map. Valkey is the Linux Foundation fork after Redis went dual-license. Use for `path_signature → node_id` + cached sentence pools |
| **Dragonfly** | <1ms | Redis-compatible, 25x faster on multi-key ops. Drop-in replacement for high-concurrency retrieval |
| **KeyDB** | <1ms | Redis fork with multithread I/O. Simpler than Dragonfly |

### Storage & Analytical Filter

| Option | Best For | Notes |
|--------|----------|-------|
| **DuckDB** | Bitmask AND filter + ORDER BY on large pools | Columnar, embedded like SQLite but 10-100x faster on analytical queries. Zero-copy vectorized filter on bitmask + rank |
| **Turso (libSQL)** | Global edge deployment, read-heavy | SQLite-compatible, embedded replicas. If engine needs to be close to collectors |
| **SurrealDB** | Replacing Redis + SQLite + vector DB with one tool | Multi-model (document + graph + vector), Rust-based, single binary. Hash lookup + bitmask filter + vector search in one query |

### Soft/Fallback Matching — Vector Similarity

| Option | Latency | Notes |
|--------|---------|-------|
| **Qdrant** | <10ms | Rust-based, gRPC + REST. Payload filtering (bitmask) during vector search — eliminates two-step retrieve-then-filter |
| **Weaviate** | <20ms | GraphQL + REST, built-in vectorizer modules. Skip managing embeddings separately |
| **LanceDB** | <5ms | Serverless, embedded, Rust-based, zero-copy. Like DuckDB but for vectors. No server to run |
| **ChromaDB** | <15ms | Python-native, simplest to prototype. Weaker at scale (>1M vectors) |

### Search Engine — Full-Text + Vector Hybrid

| Option | Notes |
|--------|-------|
| **Elasticsearch 8 / OpenSearch** | BM25 text search + kNN vector search + bitmask filter. Overkill for pure path lookup, but powerful for "find similar sentences across whole tree" |
| **Meilisearch** | Simpler than ES, typo-tolerant search. If collectors type partial queries instead of engine extracting state |

### Recommended Stack

**Two-layer (covers 95% of retrieval at <5ms):**
1. **Redis/Valkey** — hot-path O(1) lookup (`path_signature → node_id`, `node_id → sentence_pool`)
2. **DuckDB** — analytical filter-rank (bitmask AND + ORDER BY win_rate DESC, sas DESC)

**One-tool alternative:** **SurrealDB** — hash lookup + bitmask filter + vector search in single query against single database. Less operational complexity, younger ecosystem.

**Add later if needed:** **Qdrant** for soft/fallback matching at scale.

**Passing criteria:**
- Covers all 5 migration steps
- Each step has before/after architecture
- Retrieval latency target: < 50ms at 100K nodes (hash/SQL lookup, no traversal)
- Storage migration from JSON to SQLite DDL specified
- Build-time strategy for incremental rebuild documented
