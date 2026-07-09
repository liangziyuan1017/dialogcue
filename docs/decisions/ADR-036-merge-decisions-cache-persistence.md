---
id: ADR-036
title: "Persist merge decisions cache after incremental tree build"
doc_kind: decision
feature_ids: [F015, F004]
topics: [incremental, tree, merge, reproducibility, cache]
status: accepted
created: 2026-07-09
updated: 2026-07-09
schema_version: 1
---

# Persist Merge Decisions Cache After Incremental Tree Build

## What

`merge_dialogs` loads the merge decisions cache (`merge_decisions.json`) to reuse prior LLM merge choices, but never saved it. After the incremental tree build, `_save_merge_cache` now persists the (possibly extended) cache so LLM merge decisions for new records are reproducible.

## Why

- Without saving, a second incremental run re-asks the LLM for the same merges, producing non-deterministic tree growth and wasting LLM calls.
- The cache is the record of *which* consecutive collector turns were merged for each dialog; persisting it makes incremental appends deterministic given the same cache seed.

## Decision

Call `_save_merge_cache(merge_cache)` in `_phase2_tree` immediately after `merge_dialogs` returns, before scoring/DB upsert.

## Impact

| Component | Change |
|-----------|--------|
| `src/add_records.py` | `_phase2_tree` saves merge cache after `merge_dialogs` |
| `src/f004_decision_tree/data/merge_decisions.json` | now updated on every incremental append |

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Save inside `merge_dialogs` | `merge_dialogs` is also used by full-rebuild paths; saving there changes unrelated behavior |
| Skip cache, re-merge every run | Non-deterministic; redundant LLM cost |
