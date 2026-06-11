# F004: Decision Tree Construction — Implementation Plan

**Feature:** F004 — `docs/features/F004-decision-tree-construction.md`
**Goal:** Build a collector decision tree where nodes are collector action points, branches are customer response profiles (facts + emotions), and willingness labels each sentence in the pool.
**Acceptance Criteria:**
- Root node has `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`, `customer_willingness`
- All 31 call_ids appear in at least one `source_call_ids`
- Keywords lexicographically sorted at every node
- Branches keyed by (facts, emotions) only — willingness is a sentence label
- Fallback via progressive tag removal works when exact branch not found
**Architecture:** Nodes = collector actions. Branches = customer (facts, emotions). Willingness tags each sentence. Merge rule: same (facts, emotions) = same branch regardless of willingness. See ADR-011.
**Tech Stack:** Python, pytest

---

### Task 1: State Path Extraction (revised)

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `extract_state_paths(record)` returns alternating (collector_action, customer_response) pairs where customer_response key is (facts, emotions) and willingness is attached to the next collector sentence
**Step 2: Run test to verify it fails**
**Step 3: Implement revised `extract_state_paths()`**
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Tree Construction with Branch Merging

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `build_tree(records)` branches on (facts, emotions), merges willingness into sentence labels, and produces branching structure (not chains)
**Step 2: Run test to verify it fails**
**Step 3: Implement revised `build_tree()`** — insert paths, merge on (facts, emotions), tag sentences with `customer_willingness`, sort keywords
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Fallback via Progressive Tag Removal

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test fallback removes emotions then facts
**Step 2: Run test to verify it fails**
**Step 3: Implement revised `find_node()` with fallback**
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Output, Validation & Regeneration

**Files:**
- Modify: `src/build_decision_tree.py`
- Create: `src/decision_tree.json`

**Step 1: Write failing test** — test real data: all 31 call_ids, all leaf nodes have sentence_pool, keywords sorted, sentences have customer_willingness
**Step 2: Run test to verify it fails**
**Step 3: Implement `write_decision_tree()` and regenerate**
**Step 4: Run test to verify it passes**
**Step 5: Commit**
