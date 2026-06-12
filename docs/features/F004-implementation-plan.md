# F004: Decision Tree Construction — Implementation Plan

**Feature:** F004 — `docs/features/F004-decision-tree-construction.md`
**Goal:** Add opening/ending gesture support to the decision tree. Every dialog has a start node (opening gesture) and an end node (ending gesture). Dialogs without proper closings route to an `abrupt_end` node.
**Acceptance Criteria:**
- Root node sentence_pool entries have `gesture_type: "opening"` for greeting sentences
- Tree has an `abrupt_end` end node with `gesture_type: "ending"`
- Every dialog path terminates at either a proper end node or `abrupt_end`
- Ending gesture sentences have `gesture_type: "ending"`
- Dialogs without proper closing are routed to `abrupt_end` node
**Architecture:** Extend existing tree with gesture_type on sentence entries. Add `abrupt_end` as a special terminal node. Detect closing actions (goodbye, closure, etc.) vs abrupt endings (no closing turn). See ADR-011.
**Tech Stack:** Python, pytest

---

### Task 1: Opening Gesture Detection

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that greeting sentences in root node sentence_pool have `gesture_type: "opening"`
**Step 2: Run test to verify it fails**
**Step 3: Implement** — tag greeting sentences with `gesture_type: "opening"` in `build_tree()`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Ending Gesture Detection

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that closing sentences (action: closure, goodbye) have `gesture_type: "ending"` and are placed in an end node
**Step 2: Run test to verify it fails**
**Step 3: Implement** — detect closing actions in each record, tag with `gesture_type: "ending"`, add to end nodes
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Abrupt End Node

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that dialogs without a closing action have their last state routed to an `abrupt_end` node with `gesture_type: "ending"`
**Step 2: Run test to verify it fails**
**Step 3: Implement** — after processing each record, if no closing action found, add `abrupt_end` child to the last node with sentence_pool containing the last collector turn tagged `gesture_type: "ending"`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Path Termination Guarantee

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that every leaf node in the tree is either a proper end node (has ending gesture) or the `abrupt_end` node
**Step 2: Run test to verify it fails**
**Step 3: Implement** — ensure `build_tree()` guarantees all paths terminate at end nodes or abrupt_end
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 5: Regenerate & Validate Real Data

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`
- Create: `src/decision_tree.json`

**Step 1: Write failing test** — test real data: root has opening gestures, abrupt_end exists, all leaf nodes are end nodes or abrupt_end
**Step 2: Run test to verify it fails**
**Step 3: Implement** — regenerate `decision_tree.json` with new structure
**Step 4: Run test to verify it passes**
**Step 5: Commit**
