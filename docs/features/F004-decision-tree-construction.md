---
id: F004
name: Decision Tree Construction
status: planned
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

Every dialog has a **start node** and an **end node**:
- **Start node** (`state_id: "initial_contact"`) captures the **opening gesture** — greeting, self-introduction, purpose statement
- **End node** captures the **ending gesture** — proper closing like goodbye, confirmation, or well-wishes
- If a dialog has no proper ending (e.g., customer hangs up, conversation cut short), it leads to an **"abrupt_end"** end node
- The tree structure guarantees every path from root to leaf passes through a start node and terminates at either a proper end node or the `abrupt_end` node
- Opening and ending gestures are recorded as `gesture_type: "opening"` and `gesture_type: "ending"` on their sentence entries

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
- [ ] Root node sentence_pool entries have `gesture_type: "opening"` for greeting sentences
- [ ] Tree has an `abrupt_end` end node with `gesture_type: "ending"`
- [ ] Every dialog path terminates at either a proper end node or `abrupt_end`
- [ ] Ending gesture sentences have `gesture_type: "ending"`
- [ ] Dialogs without proper closing are routed to `abrupt_end` node

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
- **Start/end node model**: Every dialog has a start node (opening gesture) and an end node (ending gesture). Abrupt endings route to a shared `abrupt_end` node. This gives the tree a well-defined entry/exit structure.

## Files

| File | Purpose |
|------|---------|
| `src/build_decision_tree.py` | Decision tree construction logic |
| `src/test_build_decision_tree.py` | Tests (15 passing) |
| `src/decision_tree.json` | Generated output (96 nodes) |
| `src/tree_explorer.html` | Interactive tree visualizer |
