# F004: Decision Tree Construction — Implementation Plan

**Feature:** F004 — `docs/features/F004-decision-tree-construction.md`
**Goal:** Add opening/ending gesture support to the decision tree. The tree has exactly 1 opening node (root) and 2 consolidated end nodes (`normal_end` + `abrupt_end`) as direct children of root. All properly-closed dialogs converge into `normal_end`; all dialogs without closings converge into `abrupt_end`.
**Acceptance Criteria:**
- Root node sentence_pool entries have `gesture_type: "opening"` for greeting sentences
- Tree has exactly one `normal_end` node and one `abrupt_end` node, both with `gesture_type: "ending"`
- Both end nodes are direct children of root (consolidated endpoints)
- Every dialog path terminates at either `normal_end` or `abrupt_end`
- Ending gesture sentences have `gesture_type: "ending"`
- Dialogs without proper closing are routed to `abrupt_end` node
**Architecture:** Extend existing tree with gesture_type on sentence entries. Consolidate all ending sentences into a single `normal_end` node and all abrupt terminations into a single `abrupt_end` node as root children. Tree renders vertically (top-to-bottom). See ADR-011.
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

**Step 1: Write failing test** — test that closing sentences (action: closure, goodbye) have `gesture_type: "ending"`
**Step 2: Run test to verify it fails**
**Step 3: Implement** — detect closing actions in each record, tag with `gesture_type: "ending"`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Consolidated End Nodes

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that tree has exactly one `normal_end` and one `abrupt_end` as root children
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_consolidate_endpoints()` collects all ending sentences into `normal_end`, strips scattered terminal nodes, adds both end nodes as root children
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Path Termination Guarantee

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that both end nodes exist and are root children
**Step 2: Run test to verify it fails**
**Step 3: Implement** — ensure `build_tree()` guarantees consolidated endpoint structure
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 5: Regenerate & Validate Real Data

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`
- Create: `src/decision_tree.json`

**Step 1: Write failing test** — test real data: root has opening gestures, exactly 1 normal_end + 1 abrupt_end as root children
**Step 2: Run test to verify it fails**
**Step 3: Implement** — regenerate `decision_tree.json` with consolidated structure
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 6: Vertical Tree Visualizer (Cytoscape.js + dagre)

**Files:**
- Modify: `src/tree_explorer.html`

**Step 1: Implement** — Replace SVG renderer with Cytoscape.js graph engine + dagre hierarchical layout. Convert tree JSON to Cytoscape.js adjacency format (nodes + edges). Style nodes by type: round-rectangle (opening/decision), ellipse (normal end), triangle (abrupt end). Edges carry branch labels. Supports zoom, pan, drag, click-to-inspect.
**Step 2: Verify** — open in browser, confirm tree renders vertically with 1 opening at top, 2 end nodes at bottom, all paths terminate correctly
**Step 3: Commit**
