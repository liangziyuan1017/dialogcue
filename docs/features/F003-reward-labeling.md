---
id: F003
name: Reward Labeling
status: planned
owner: agent
source: plan_feature_base.md
created: 2026-06-11
depends_on: F001
---

# F003: Reward Labeling

## Why

Downstream features (F004 decision tree, F005 quality scoring, F006 retrieval engine) need a binary reward signal per conversation to compute win rates and rank collector scripts. Without reward labeling, there is no ground truth for which collector actions succeed.

## What

Determine R ∈ {0, 1} per conversation:
- LLM detects repayment commitment triggers in final turns
- Counterfactual verification credits the preceding collector action
- Cross-validate against `plan_evaluation`
- Output to `/src/output_rewarded.py`

### Passing Criteria

- Every record has `reward` ∈ {0, 1}
- Every R=1 record has `reward_evidence` and `reward_action_credit`
- R=1 records consistent with `plan_evaluation` (mismatches flagged as warnings)
- No R=0 record has `reward_action_credit`

## Acceptance Criteria

- [ ] All 31 records have `reward` ∈ {0, 1}
- [ ] Every R=1 record has `reward_evidence` with `trigger_text` and `trigger_turn_index`
- [ ] Every R=1 record has `reward_action_credit` with turn details
- [ ] R=1 records consistent with `plan_evaluation`
- [ ] No R=0 record has `reward_action_credit`

## Dependencies

- F001 (Data Schema Alignment) — complete, `output_aligned.py` exists

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F003 spec

## Implementation Plan

See [F003-implementation-plan.md](F003-implementation-plan.md)

## Files

| File | Purpose |
|------|---------|
| `src/reward_label.py` | Reward labeling logic |
| `src/test_reward_label.py` | Tests (14 passing) |
| `src/output_rewarded.py` | Generated output |
