# F004: Decision Tree Construction — Implementation Plan

**Feature:** F004 — `docs/features/F004-decision-tree-construction.md`
**Goal:** Build state-transition decision tree from annotated conversations, merge identical states, accumulate collector sentence pools, implement fallback via progressive tag removal.
**Acceptance Criteria:**
- Root node has `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`
- All 31 call_ids appear in at least one `source_call_ids`
- Keywords lexicographically sorted at every node
- Fallback via progressive tag removal works
**Architecture:** Extract state paths from each conversation's annotated turns. Build tree by inserting paths node-by-node, merging nodes with identical composite state keys. Collector turns at each node accumulate into `sentence_pool`. Fallback removes tags progressively (emotions → facts) until match.
**Tech Stack:** Python, pytest

---

### Task 1: State Path Extraction

**Files:**
- Create: `src/build_decision_tree.py`
- Test: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `extract_state_paths(record)` returns list of (state_key, collector_text) tuples from annotated turns
**Step 2: Run test to verify it fails**
**Step 3: Implement `extract_state_paths()`** — iterate turns, build composite state key from facts/emotions/willingness/action, collect collector sentences
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Tree Construction & Merging

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `build_tree(records)` returns tree with root `initial_contact`, merged nodes, and sentence pools
**Step 2: Run test to verify it fails**
**Step 3: Implement `build_tree()`** — insert paths into tree, merge identical state keys, accumulate sentence_pool with script_text/script_id/source_call_ids, sort keywords
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Fallback via Progressive Tag Removal

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `find_node(tree, state_key)` returns exact match or fallback match with progressively removed tags
**Step 2: Run test to verify it fails**
**Step 3: Implement `find_node()` with fallback** — try exact match, then remove emotions, then remove facts one-by-one
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Output & Validation

**Files:**
- Modify: `src/build_decision_tree.py`
- Create: `src/decision_tree.json`

**Step 1: Write failing test** — test that output has all 31 call_ids, all leaf nodes have sentence_pool, keywords sorted
**Step 2: Run test to verify it fails**
**Step 3: Implement `write_decision_tree()`** — build tree from all records, validate, write to JSON
**Step 4: Run test to verify it passes**
**Step 5: Commit**
