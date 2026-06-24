---
name: F012
title: State Extraction Module — LLM-first + Keyword Fallback
status: planned
depends_on: [F010, F011]
created: 2026-06-24
updated: 2026-06-24
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F012: State Extraction Module — LLM-first + Keyword Fallback

## Goal

Create `src/f006_retrieval_engine/state_extraction.py` with LLM-first state extraction, PostgreSQL keyword fallback, and state accumulation with dedup.

Covers **Step 7** of `stepwise_modification.md`.

## Passing Criteria

- `extract_state("我现在没钱还", taxonomy)` returns `{facts: ["financial_hardship"], ...}`
- `extract_state_llm()` returns `{facts, emotions, actions, confidence, method: "llm"}`
- `extract_state_keyword()` returns `{facts, emotions, actions, confidence, method: "keyword"}`
- `extract_state()` tries LLM first, falls back to keyword on failure
- `merge_state({facts: ["a"]}, {facts: ["b"]})` → `{facts: ["a", "b"]}`
- `merge_state({facts: ["a"]}, {facts: ["a"]})` → `{facts: ["a"]}` (dedup)
- Insertion order preserved (first-seen order)

## Files

- NEW: `src/f006_retrieval_engine/state_extraction.py`
- NEW: `src/tests/f006_retrieval_engine/test_state_extraction.py`
