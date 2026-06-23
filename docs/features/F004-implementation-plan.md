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
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that greeting sentences in root node sentence_pool have `gesture_type: "opening"`
**Step 2: Run test to verify it fails**
**Step 3: Implement** — tag greeting sentences with `gesture_type: "opening"` in `build_tree()`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Ending Gesture Detection

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that closing sentences (action: closure, goodbye) have `gesture_type: "ending"`
**Step 2: Run test to verify it fails**
**Step 3: Implement** — detect closing actions in each record, tag with `gesture_type: "ending"`
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Consolidated End Nodes

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that tree has exactly one `normal_end` and one `abrupt_end` as root children
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_consolidate_endpoints()` collects all ending sentences into `normal_end`, strips scattered terminal nodes, adds both end nodes as root children
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Path Termination Guarantee

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that both end nodes exist and are root children
**Step 2: Run test to verify it fails**
**Step 3: Implement** — ensure `build_tree()` guarantees consolidated endpoint structure
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 5: Regenerate & Validate Real Data

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
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

### Task 7: collector_action Field on Sentences

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that every sentence entry has `collector_action` field
**Step 2: Run test to verify it fails**
**Step 3: Implement** — propagate `collector_action` from the source turn's action label to each sentence entry
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 8: Dialog Tracer with Animated Walkthrough

**Files:**
- Modify: `src/tree_explorer.html`
- Create: `src/dialog_records.json`

**Step 1: Implement** — Add dialog tracer panel: select a call record, walk through turns step-by-step, highlight corresponding path in tree. Auto-play animation with flowing node highlights.
**Step 2: Implement** — Flowing highlight: only current node glows, panel scrolls to keep active step near top
**Step 3: Verify** — open in browser, select a call, confirm path highlights match dialog flow
**Step 4: Commit**

### Task 9: Bundled JS Libraries

**Files:**
- Create: `src/cytoscape.min.js`
- Create: `src/dagre.min.js`
- Create: `src/cytoscape-dagre.min.js`
- Modify: `src/tree_explorer.html`

**Step 1: Implement** — Download and bundle Cytoscape.js, dagre, cytoscape-dagre locally. Update HTML to reference local files instead of CDN.
**Step 2: Verify** — open in browser offline, confirm tree renders correctly
**Step 3: Commit**

### Task 10: Regenerate & Final Validation

**Files:**
- Modify: `src/decision_tree.json`

**Step 1: Regenerate** — run `build_decision_tree.py` to produce final `decision_tree.json` with all features (gestures, collector_action, consolidated endpoints)
**Step 2: Verify** — 333 nodes, 222 leaves, 31/31 call_ids, all AC pass
**Step 3: Commit**

### Task 11: Fact-by-Fact Walking & Local Tree Building

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Implement** — Walk each segment's facts and emotions one at a time in `build_tree`, creating single-key nodes. Remove global node search (`_find_node_by_branch_key`). Each record's path is built locally.
**Step 2: Write tests** — `test_no_composite_branch_keys`, `test_emotion_cycle_*` updated for new structure
**Step 3: Verify** — all tests pass, no composite branch keys in tree
**Step 4: Commit**

### Task 12: Post-Processing Pipeline (Split, Merge, Collapse, Propagate)

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`
- Create: `src/test_record_coverage.py`

**Step 1: Implement** — `_split_composite_nodes`, `_merge_sibling_facts`, `_collapse_redundant_facts`, `_split_by_action`, `_propagate_facts` as post-processing pipeline in `write_decision_tree`
**Step 2: Implement** — `state=None` turns captured without `collector_action` (no synthetic `other`), empty-sentence segments, no early break on greetings
**Step 3: Write tests** — `test_no_redundant_fact_nodes`, `test_inherited_facts_strictly_from_parent_chain`, `test_sentences_under_action_nodes_for_fact_emotion_parents`, record coverage tests
**Step 4: Regenerate** — `decision_tree.json` (333 nodes, 222 leaves)
**Step 5: Verify** — 34 unit tests + 10 coverage tests pass
**Step 6: Commit**

### Task 13: UI Enhancements (Dialog View, Info Panel, No-Cache Server)

**Files:**
- Modify: `src/tree_explorer.html`
- Modify: `src/serve_tree.py`

**Step 1: Implement** — Dialog view toggle, info panel with inherited facts and turn matching, cache-busting on JSON fetches, NoCacheHandler + ReusableTCPServer
**Step 2: Implement** — Action-to-end edges, end node positioning, depth spacing, action/emotion node styling, label prefix stripping
**Step 3: Verify** — open in browser, confirm all UI features work
**Step 4: Commit**

### Task 14: Rendering Fixes (Action Type, Depth Layout, Edge Styling)

**Files:**
- Modify: `src/tree_explorer.html`
- Create: `src/test_ui_rendering.py`

**Step 1: Fix** — Remove empathy/pressure emotion-type override; all action nodes render as action type (diamond, amber)
**Step 2: Fix** — Depth-based Y positioning using actual `_depth` instead of dagre rank snapping; enforceParentAboveChild ensures child strictly below parent
**Step 3: Fix** — Arrow scale 1.4x on all edges; action-flow edges muted slate (#475569)
**Step 4: Write tests** — 20 tests covering type/shape/color consistency, depth separation, parent-above-child, ancestor-above-descendant, back-edge handling
**Step 5: Verify** — 64/64 tests pass
**Step 6: Commit**

### Task 15: Remove Synthetic `other` Action Category

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`
- Modify: `src/test_record_coverage.py`
- Modify: `src/test_ui_rendering.py`
- Modify: `src/decision_tree.json`

**Step 1: Fix** — Collector turns without action label captured without `collector_action` key (not `other`); `_split_by_action` keeps unassigned sentences in parent pool
**Step 2: Regenerate** — `decision_tree.json` (333 nodes, 7 real action categories)
**Step 3: Update tests** — Fix `test_sentences_without_action_have_no_collector_action_key`, update coverage test for `collector_no_action` type, remove `other` from expected actions
**Step 4: Verify** — 64/64 tests pass
**Step 5: Commit**

### Task 16: View Mode Dedicated Renderer

**Files:**
- Modify: `src/tree_explorer.html`

**Step 1: Implement** — `buildViewGraph` with sequential vertical flow (preset layout, Y = row × 320)
**Step 2: Implement** — Back edges as dashed slate lines, source offset rightward to avoid crossing; `cy.fit(undefined, 80)` for comfortable zoom
**Step 3: Remove** — `assignCompactLayout` and `compact` parameter (no longer needed)
**Step 4: Verify** — open in browser, select record 13, confirm no overlap and comfortable zoom
**Step 5: Commit**
