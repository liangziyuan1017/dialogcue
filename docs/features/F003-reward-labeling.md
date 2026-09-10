---
REMOVED_FIELD_id: F003
name: Reward Labeling
status: complete
owner: agent
source: ROADMAP.md
created: 2026-06-11
depends_on: F001
merged: 2026-06-11 76b7c5c
---

# F003: Reward Labeling

## Why

Downstream features (F004 decision tree, F005 quality scoring, F006 retrieval engine) need a binary reward signal per conversation to compute win rates and rank collector scripts. Without reward labeling, there is no ground truth for which collector actions succeed.

## What

Determine R ∈ {0, 1} per conversation:
- LLM detects repayment commitment triggers in final turns
- Counterfactual verification credits the preceding collector action
- Cross-validate against `plan_evaluation`
- Output to `/src/f003_reward_labeling/output_rewarded.py`

### Passing Criteria

- Every record has `reward` ∈ {0, 1}
- Every R=1 record has `reward_evidence` and `reward_action_credit`
- R=1 records consistent with `plan_evaluation` (mismatches flagged as warnings)
- No R=0 record has `reward_action_credit`

## Acceptance Criteria

- [x] All 31 records have `reward` ∈ {0, 1}
- [x] Every R=1 record has `reward_evidence` with `trigger_text` and `trigger_turn_index`
- [x] Every R=1 record has `reward_action_credit` with turn details
- [x] R=1 records consistent with `plan_evaluation`
- [x] No R=0 record has `reward_action_credit`

## Dependencies

- F001 (Data Schema Alignment) — complete, `output_aligned.py` exists

## Links

- [ROADMAP.md](../ROADMAP.md) — dependency graph + architecture decisions

## Implementation Plan

See [implementation-plan.md](F003-implementation-plan.md)

## Review Notes

**Review 1:** `reward_action_credit` should include an `explanation` field (<100 words) describing the conversation logic flow (facts, emotions, willingness, collector actions) rather than just copying data from `reward_evidence`.
- Resolution: Added `_build_explanation_prompt()` that sends annotated turns to LLM, generates causal chain explanation. Added `explanation` field to `reward_action_credit`. New test `test_reward_action_credit_has_explanation` passes.
- Status: Fixed ✅

## Files

| File | Purpose |
|------|---------|
| `src/f003_reward_labeling/reward_label.py` | Reward labeling logic |
| `src/test_reward_label.py` | Tests (14 passing) |
| `src/f003_reward_labeling/output_rewarded.py` | Generated output |
