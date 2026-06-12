---
id: F004
name: Decision Tree Construction
status: review
owner: agent
source: plan_feature_base.md
created: 2026-06-11
updated: 2026-06-12
depends_on: F003
---

# F004: Decision Tree Construction

## Why

The retrieval engine (F006) needs a traversable decision tree to recommend collector scripts given a customer state. Without the tree, there is no structure to match real-time conversation states against historical successful paths. Additionally, every dialog has an opening gesture and an ending gesture — these must be explicitly represented as start and end nodes in the tree structure.

## What

Build a **collector decision tree** where:
- **Nodes** are decision points keyed by customer response profile `(facts, emotions)`
- **Sentence pools** at each node contain collector scripts, each tagged with `customer_willingness`
- **Willingness** is a label on sentences, NOT a branching factor
- **Branches** diverge only when customer introduces new facts or new emotions
- Fallback via progressive tag removal when exact branch not found
- Output to `/src/decision_tree.json`

### Dialog Gestures (Opening & Ending)

Every dialog has a **start node** and converges to one of two **end nodes**:
- **Start node** (`state_id: "initial_contact"`) — the single root capturing the **opening gesture** (greeting, self-introduction, purpose statement). There is exactly one opening node in the tree.
- **Normal end node** (`state_id: "normal_end"`) — all properly-closed dialogs converge here. Contains all ending gesture sentences (goodbye, confirmation, well-wishes).
- **Abrupt end node** (`state_id: "abrupt_end"`) — all dialogs without proper closings converge here. Contains the abrupt-end marker sentence.
- The tree has exactly **3 terminal-adjacent nodes**: 1 opening (root), 1 normal_end, 1 abrupt_end. Both end nodes are direct children of root.
- Opening and ending gestures are recorded as `gesture_type: "opening"` and `gesture_type: "ending"` on their sentence entries
- The tree is rendered **vertically** (top-to-bottom): opening at top, decision branches in middle, two end nodes at bottom

### Architecture (ADR-011)

Nodes = collector action points. Branches = customer (facts, emotions). Willingness tags each sentence. A new decision point is created ONLY when the customer introduces new facts or new emotions. Willingness-only changes (e.g., conditional → negotiating) do NOT create new branches.

### Merge List (7 groups merged from 93 → 64 decision points)

| # | facts | emotions | Willingness levels merged |
|---|-------|----------|--------------------------|
| 1 | ∅ | ∅ | conditional(15) + weak(10) + negotiating(6) + strong(4) |
| 2 | financial_hardship | ∅ | weak(4) + none(4) + negotiating(1) |
| 3 | ∅ | pleading | none(1) + conditional(1) + negotiating(1) |
| 4 | financial_hardship, multiple_debts | ∅ | conditional(1) + weak(1) + none(1) |
| 5 | multiple_debts | ∅ | conditional(1) + none(1) |
| 6 | ∅ | skepticism | negotiating(1) + none(1) |
| 7 | financial_hardship | helplessness | none(1) + resistant(1) |

### Passing Criteria

- Tree has root node with `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`, `customer_willingness`
- All 31 conversations represented (every call_id in at least one `source_call_ids`)
- Keywords lexicographically sorted at every node

## Acceptance Criteria

- [x] Root node has `state_id: "initial_contact"`
- [x] Every leaf node has non-empty `sentence_pool`
- [x] Every sentence entry has `script_text`, `script_id`, `source_call_ids`, `customer_willingness`
- [x] All 31 call_ids appear in at least one `source_call_ids`
- [x] Keywords lexicographically sorted at every node
- [x] Branches keyed by (facts, emotions) only — willingness is a sentence label
- [x] Fallback via progressive tag removal works when exact branch not found
- [x] Tree is branching (not chain-like): single-child ratio < 80%
- [x] Root node sentence_pool entries have `gesture_type: "opening"` for greeting sentences
- [x] Tree has exactly one `normal_end` node and one `abrupt_end` node, both with `gesture_type: "ending"`
- [x] Both end nodes are direct children of root (consolidated endpoints)
- [x] Every dialog path terminates at either `normal_end` or `abrupt_end`
- [x] Ending gesture sentences have `gesture_type: "ending"`
- [x] Dialogs without proper closing are routed to `abrupt_end` node

## Dependencies

- F003 (Reward Labeling) — complete, `output_rewarded.py` exists

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F004 spec
- [ADR-011](../../decisions/ADR-011-decision-tree-approach.md) — Architecture decision

## Implementation Plan

See [F004-implementation-plan.md](F004-implementation-plan.md)

## Design Decisions

- **Willingness as sentence label, not branch key**: Same (facts, emotions) = same decision point regardless of willingness. Collector sees "under financial_hardship, when customer is weak I say X, when negotiating I say Y" — both under the same branch.
- **Rare facts kept as branches**: Not bucketed into `_other` — data will broaden.
- **Segment-based extraction**: Each conversation is decomposed into segments of (customer branch key → collector sentences), not individual turns. This avoids the chain problem.
- **Start/end node model**: The tree has exactly 1 opening node (root) and 2 consolidated end nodes (`normal_end` and `abrupt_end`) as direct children of root. All properly-closed dialogs converge into `normal_end`; all dialogs without proper closings converge into `abrupt_end`. This gives the tree a clean vertical structure: opening at top → decision branches → two end nodes at bottom.
- **Consolidated endpoints**: Rather than scattering many `abrupt_end` leaves throughout the tree, all ending sentences are collected into a single `normal_end` node and all abrupt terminations into a single `abrupt_end` node. This ensures the tree has exactly 2 terminal nodes regardless of data size.
- **Cytoscape.js + dagre layout**: Tree is rendered as an interactive graph using Cytoscape.js with the dagre hierarchical layout engine. Supports zoom, pan, drag, click-to-inspect. Nodes are styled by type: rectangles (opening/decision), ellipse (normal end), triangle (abrupt end). Edges carry branch labels (facts|emotions).

## Files

| File | Purpose |
|------|---------|
| `src/build_decision_tree.py` | Decision tree construction logic |
| `src/test_build_decision_tree.py` | Tests (27 passing) |
| `src/decision_tree.json` | Generated output (60 nodes) |
| `src/tree_explorer.html` | Interactive vertical tree visualizer (Cytoscape.js + dagre) |
