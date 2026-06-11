---
id: F004
name: Decision Tree Construction
status: planned
owner: agent
source: plan_feature_base.md
created: 2026-06-11
depends_on: F003
---

# F004: Decision Tree Construction

## Why

The retrieval engine (F006) needs a traversable decision tree to recommend collector scripts given a customer state. Without the tree, there is no structure to match real-time conversation states against historical successful paths.

## What

Build state-transition decision tree from annotated conversations:
- Extract paths `S₀ → a₀ → S₁ → a₁ → ... → Sₙ` from each conversation
- Merge identical/near-identical state sequences into shared nodes
- Accumulate historical collector sentences at each node as `sentence_pool`
- Implement fallback via progressive tag removal
- Output to `/src/decision_tree.json`

### Passing Criteria

- Tree has root node with `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`
- All 31 conversations represented (every call_id in at least one `source_call_ids`)
- Keywords lexicographically sorted at every node

## Acceptance Criteria

- [ ] Root node has `state_id: "initial_contact"`
- [ ] Every leaf node has non-empty `sentence_pool`
- [ ] Every sentence entry has `script_text`, `script_id`, `source_call_ids`
- [ ] All 31 call_ids appear in at least one `source_call_ids`
- [ ] Keywords lexicographically sorted at every node
- [ ] Fallback via progressive tag removal works when exact state not found

## Dependencies

- F003 (Reward Labeling) — complete, `output_rewarded.py` exists

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F004 spec

## Implementation Plan

See [F004-implementation-plan.md](F004-implementation-plan.md)

## Files

| File | Purpose |
|------|---------|
| `src/build_decision_tree.py` | Decision tree construction logic |
| `src/test_build_decision_tree.py` | Tests |
| `src/decision_tree.json` | Generated output |
