---
id: F015
name: Incremental Record Append
status: planned
owner: agent
related_features: [F000, F001, F003, F004, F005, F007]
topics: [incremental, tree, database, embeddings, taxonomy]
doc_kind: spec
created: 2026-07-09
updated: 2026-07-09
spec: new_record_plan.md
---

# F015: Incremental Record Append

> **Status**: planned | **Owner**: agent | **Priority**: P0
>
> **Spec**: `new_record_plan.md` — seamless incremental append of new records to the decision tree and PostgreSQL database without full rebuild.

## Why

The current pipeline requires a full rebuild to add new records — re-running all cleaning, labeling, tree construction, scoring, and DB population from scratch. This is expensive (~105+ LLM calls) and risks modifying existing data. We need an incremental path that appends new records at every stage while leaving the existing 103 records intact.

## What

A single orchestrator (`src/add_records.py`) that:

1. **Pre-check** — gates on `call_id` uniqueness (no collision with existing, no dups in batch).
2. **Upstream incremental** — cleaning + labeling + alignment + reward for only the new records (append to existing outputs).
3. **Incremental tree** — `merge_dialogs` loads existing tree, adds new branches/sentences only.
4. **Targeted DB upsert** — insert new nodes/sentences, recompute scores only in affected nodes, freeze unaffected.
5. **Embed only new sentences** — DB as embedding cache.
6. **Taxonomy keyword upsert** — dedup migration + unique index + frequency update in place.
7. **Post-success hook** — append records from `new_data.jsonl` to `matched_data.jsonl`.

## Input

- New records file: `data/data_input/new_data.jsonl` (user always places new data here)
- Existing canonical data: `data/data_input/matched_data.jsonl` (103 records)

## Output

- Existing outputs appended with new records (cleaning, labeling, alignment, reward)
- `decision_tree.json` extended with new branches/sentences
- `decision_tree_scored.json` recomputed for affected nodes
- PostgreSQL `nodes`, `sentences`, `taxonomy_keywords` updated incrementally
- On success: new records appended to `matched_data.jsonl`

## Success Criteria

- `output_rewarded.py` count == 105; first 103 `call_id`s unchanged
- All old node `path_signature`s still present in tree (superset check)
- DB `sentences` count increased by exactly new sentences; no existing `script_id` deleted
- `taxonomy_keywords` has zero duplicate groups post-dedup
- 2 new `call_id`s present in `sentences` via `script_id LIKE '<new_call_id>_%'`
- `matched_data.jsonl` gains the 2 new records on success

## Files Touched

| File | Change | New? |
|---|---|---|
| `src/check_new_records.py` | Pre-check gate (Phase 0) | new |
| `src/add_records.py` | Incremental orchestrator (Phase 6) + append hook | new |
| `src/f000_keyword_discovery/discover_keywords.py` | Add `label_new_records()` helper | modify |
| `src/f004_decision_tree/build_decision_tree.py` | Fix `merge_dialogs` transforms (CR-2); add `write_dialog_records_incremental` | modify |
| `src/f007_infrastructure/db.py` | Dedup migration, unique index, upsert/query methods | modify |
| `src/f005_context_scoring/score_tree.py` | Replace inline keyword insert with `db.upsert_taxonomy_keywords` | modify |
