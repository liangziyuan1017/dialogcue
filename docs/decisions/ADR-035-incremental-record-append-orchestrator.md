---
REMOVED_FIELD_id: ADR-035
title: "Incremental record append orchestrator (single-pass, append-only)"
doc_kind: decision
feature_ids: [F015]
topics: [incremental, tree, database, embeddings, taxonomy, orchestrator]
status: accepted
created: 2026-07-09
updated: 2026-07-09
schema_version: 1
---

# Incremental Record Append Orchestrator

## What

A single orchestrator `src/add_records.py` appends new records at every pipeline stage without a full rebuild. New records flow: pre-check → cleaning → merge → label → align/relabel → reward → incremental tree → score + targeted DB upsert → taxonomy upsert → append-to-matched-data hook.

## Why

- A full rebuild costs ~105+ LLM calls and risks mutating the existing 103 records. Incremental append touches only new `call_id`s.
- Each stage appends to existing outputs (`output_labeled.py`, `output_aligned.py`, `output_rewarded.py`, `decision_tree.json`, DB) rather than regenerating them, preserving the existing 103 records verbatim.
- A pre-check gate (`check_new_records.py`) fails fast on `call_id` collision or format errors before any LLM spend.
- DB upsert is targeted: only new nodes/sentences are inserted; only sentences in affected nodes (those touched by new `call_id`s) get score updates; embeddings are computed only for new sentences (DB acts as embedding cache).

## Decision

- **Append-only outputs**: every stage loads existing output, appends new records by `call_id`, rewrites the file. No in-place mutation of existing records.
- **Targeted DB upsert**: diff against `get_existing_path_signatures` / `get_existing_script_ids`; insert new, update scores for affected existing, freeze unaffected.
- **Taxonomy dedup + unique index**: `dedup_taxonomy_keywords` removes existing duplicates; `create_taxonomy_unique_index` adds an MD5(`group_name|category|keyword`) generated column + unique index so future inserts cannot re-introduce duplicates. `upsert_taxonomy_keywords` does `ON CONFLICT (natural_key_hash) DO UPDATE SET frequency`.
- **Post-success append hook**: new records are appended to `input_data.jsonl` only after the full pipeline succeeds, so a crash leaves the canonical input unchanged.

## Impact

| Component | Change |
|-----------|--------|
| `src/add_records.py` | new — 7-phase orchestrator |
| `src/check_new_records.py` | new — Phase 0 pre-check gate |
| `src/f000_keyword_discovery/discover_keywords.py` | add `label_new_records` + `_recompute_taxonomy`; refactor `_label_turns` shared |
| `src/f004_decision_tree/build_decision_tree.py` | `merge_dialogs` transform fix; add `write_dialog_records_incremental` |
| `src/f007_infrastructure/db.py` | dedup migration, MD5 unique index, upsert/query methods |
| `src/f005_context_scoring/score_tree.py` | replace inline keyword insert with `db.upsert_taxonomy_keywords` |

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Full rebuild on new data | ~105+ LLM calls; risks mutating existing records |
| Per-stage manual scripts | No atomic pre-check gate; easy to skip a stage; no post-success hook |
| Upsert all sentences (not just affected) | Recomputing embeddings/scores for 1700+ sentences on every append is wasteful |
