# F005: Context Tagging & Quality Scoring — Implementation Plan

**Feature:** F005 — `docs/features/F005-context-tagging-quality-scoring.md`
**Goal:** Augment decision tree sentences with context bitmask (O(1) filtering), historical win rate (HWR), and script alignment score (SAS). Output to `/src/decision_tree_scored.json`.
**Acceptance Criteria:**
- Every sentence in decision_tree_scored.json has `bg_constraints` dict with 5 fields
- Every sentence has `bg_bitmask` integer (0–31)
- `bg_bitmask` correctly encodes the 5 boolean fields
- Every sentence has `win_rate` ≥ 0 and ≤ 1
- `win_rate` uses Laplace smoothing: (wins + 1) / (total + 2)
- Every sentence has `sas` ≥ 0 and ≤ 1
- `sas` computed via DeepSeek embedding cosine similarity
- `uplift_score` = 0 and `csi` = 0 with `deferred: true` on every sentence
- Bitmask AND filtering: sentence with bitmask S is compatible with context bitmask C iff (S & C) == S
- All 31 conversations represented in scored tree
- Output file: `/src/decision_tree_scored.json`
**Architecture:** Walk decision_tree.json, for each sentence look up source_call_ids in output_aligned.py (context) and output_rewarded.py (reward). Compute bitmask via intersection of source constraints, HWR via Laplace-smoothed reward ratio, SAS via DeepSeek embedding cosine similarity against best-in-node reference. See ADR-020.
**Tech Stack:** Python, pytest, DeepSeek API (via existing `llm_client.py`), numpy

---

### Task 1: Context Lookup Builder

**Files:**
- Create: `src/score_tree.py`
- Create: `src/test_score_tree.py`

**Step 1: Write failing test** — test that `_build_context_lookup()` returns dict mapping call_id → context dict for all 31 records from output_aligned.py
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_build_context_lookup()` loads output_aligned.py, returns `{r["call_id"]: r["context"] for r in results}`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Reward Lookup Builder

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test that `_build_reward_lookup()` returns dict mapping call_id → reward (0 or 1) for all 31 records from output_rewarded.py
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_build_reward_lookup()` loads output_rewarded.py, returns `{r["call_id"]: r["reward"] for r in results}`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Bitmask Encoding

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test `_encode_bitmask(context)` returns correct integer for known context dicts; test `_compute_bg_constraints(call_ids, context_lookup)` returns intersection of constraints for multi-source sentences; test `_compute_bg_bitmask(bg_constraints)` returns correct integer
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_encode_bitmask(context)` maps 5 boolean fields to bits; `_compute_bg_constraints()` collects per-source bitmasks and ANDs them; `_compute_bg_bitmask()` converts dict to integer
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: HWR Computation

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test `_compute_hwr(call_ids, reward_lookup)` returns (wins+1)/(total+2) for known R=1/R=0 call_ids; test edge cases: single R=1 → 2/3, single R=0 → 1/3, empty list → 0.5
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_compute_hwr()` counts wins/total from reward_lookup, applies Laplace smoothing
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 5: SAS Computation (DeepSeek Embeddings)

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test `_cosine_similarity(a, b)` returns 1.0 for identical vectors, 0.0 for orthogonal, correct value for known vectors; test `_compute_sas_for_pool(sentences, embeddings)` returns 1.0 for single-sentence pool, correct values for multi-sentence pool
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_get_embeddings(texts)` calls DeepSeek embedding API via llm_client; `_cosine_similarity()` using numpy; `_compute_sas_for_pool()` finds reference (highest HWR), computes cosine similarity for each sentence against reference
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 6: Scored Tree Assembly

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test `score_tree(tree, context_lookup, reward_lookup)` returns tree with all sentences augmented with bg_constraints, bg_bitmask, win_rate, sas, uplift_score, csi, deferred; test tree structure preserved (same nodes, same children)
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `score_tree()` walks tree recursively, augments each sentence in each node's sentence_pool with all computed fields; adds uplift_score=0, csi=0, deferred=true
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 7: Write Scored Tree Output

**Files:**
- Modify: `src/score_tree.py`
- Modify: `src/test_score_tree.py`

**Step 1: Write failing test** — test `write_scored_tree()` writes decision_tree_scored.json with correct structure
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `write_scored_tree()` loads decision_tree.json, calls score_tree(), writes to decision_tree_scored.json
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 8: Generate Real Scored Tree + Integration Validation

**Files:**
- Modify: `src/decision_tree_scored.json`
- Create: `src/test_score_tree_integration.py`

**Step 1: Run score_tree.py** to generate decision_tree_scored.json from real data
**Step 2: Write integration tests** — verify all 1334 sentences have bg_constraints (5 fields), bg_bitmask (0–31), win_rate (0–1), sas (0–1), uplift_score=0, csi=0, deferred=true; verify all 31 call_ids represented; verify bitmask AND filtering correctness
**Step 3: Run integration tests**
**Step 4: Commit**
