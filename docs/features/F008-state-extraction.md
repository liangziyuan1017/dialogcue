---
REMOVED_FIELD_id: F008
name: State Extraction Module
status: review
depends_on: [F007, F007b]
created: 2026-06-24
updated: 2026-07-10
review_submitted: 2026-06-25
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F008: State Extraction Module — LLM-first + Keyword Fallback

## Goal

Create `src/f008_state_extraction/state_extraction.py` with LLM-first state extraction, PostgreSQL keyword fallback, and state accumulation with dedup.

Covers **Step 7** of [F007-F009-implementation-steps.md](F007-F009-implementation-steps.md).

## Passing Criteria

- `extract_state("我现在没钱还", taxonomy)` returns `{facts: ["financial_hardship"], ...}`
- `extract_state_llm()` returns `{facts, emotions, actions, confidence, method: "llm"}`
- `extract_state_keyword()` returns `{facts, emotions, actions, confidence, method: "keyword"}`
- `extract_state()` tries LLM first, falls back to keyword on failure
- `merge_state({facts: ["a"]}, {facts: ["b"]})` → `{facts: ["a", "b"]}`
- `merge_state({facts: ["a"]}, {facts: ["a"]})` → `{facts: ["a"]}` (dedup)
- Insertion order preserved (first-seen order)

## Files

- NEW: `src/f008_state_extraction/state_extraction.py`
- NEW: `src/tests/f008_state_extraction/test_state_extraction.py`

## Implementation Plan

See [implementation-plan.md](F008-implementation-plan.md)

## Design Decisions

- **Single winner per utterance (ADR-039)**: `merge_state` only pushes the **previous** `branch_key` to `inherited_facts`/`inherited_emotions`. Non-winner labels from the same extraction are dropped — they are not added to `inherited_*`. This ensures `inherited_*` is empty on the first utterance (no prior turns to inherit from). The winner (last fact > last emotion > last action) becomes the new `branch_key`. Downstream: the retrieval engine matches shallower tree nodes instead of over-specifying the path on a single utterance.

## Links

- [ADR-039](../decisions/ADR-039-single-winner-per-utterance.md) — Single winner per utterance in merge_state
