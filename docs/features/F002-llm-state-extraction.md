---
id: F002
name: LLM State Extraction
status: planned
depends_on: [F000, F001]
---

# F002: LLM State Extraction

## Why

We need structured state labels on every turn to build the decision tree (F004). Currently only a subset of turns have manual annotations. LLM-based extraction using the F000 taxonomy will give us consistent, complete coverage across all 805 turns.

## What

For each **customer turn**, extract composite state keywords `S = { Emotion + Fact + Willingness }` via DeepSeek, using the taxonomy from F000 (`src/state_keywords.json`) as the target set.

For each **collector turn**, extract `action_type` from the F000 discovered taxonomy and preserve `action_text` verbatim.

Output to `/src/output_states.py`.

## Acceptance Criteria

- [ ] Every customer turn has `state_keywords` with at least one tag per dimension (emotion, fact, willingness)
- [ ] Every collector turn has `action_type` from the F000 discovered taxonomy and `action_text` preserved verbatim
- [ ] Labeled turns (label="1") annotated but flagged
- [ ] Resume-safe: re-run skips already-annotated turns
- [ ] All 805 turns processed

## Dependencies

- F000: `src/state_keywords.json` (taxonomy)
- F001: `src/output_aligned.py` (aligned records)

## Files

| File | Purpose |
|------|---------|
| `src/extract_states.py` | Main extraction script |
| `src/output_states.py` | Output with state annotations |
| `src/test_extract_states.py` | Tests |

## Implementation Plan

See [F002-implementation-plan.md](F002-implementation-plan.md)

## Links

- Spec: `plan_feature_base.md` F002 section
- Input: `src/state_keywords.json`, `src/output_aligned.py`
