---
id: F015
name: Incremental Record Append
status: review
owner: agent
related_features: [F000, F001, F003, F004, F005, F007]
topics: [incremental, tree, database, embeddings, taxonomy]
doc_kind: spec
created: 2026-07-09
updated: 2026-07-09
spec: new_record_plan.md
adrs: [ADR-035, ADR-036, ADR-037]
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

## Implementation

End-to-end incremental append implemented and verified. Three commits land the orchestrator, crash-recovery cleanup, and merge-cache persistence.

### Commit 1 — `d06e1dd`: incremental record append (2 new records)

- **Phase 0** (`check_new_records.py`): gates on `call_id` uniqueness vs existing `output_rewarded.py` + intra-batch dedup + `check_record` format validation.
- **Phase 1a–1e** (`add_records.py`): cleaning (LLM steps 1–3) → merge extra fields → `label_new_records` (taxonomy recompute over all labeled records) → schema alignment + relabel → reward labeling. Each stage appends only new `call_id`s to existing outputs.
- **Phase 2** (`build_decision_tree.py`): `merge_dialogs` loads existing tree + merge cache, adds new branches/sentences only. `merge_dialogs` transform chain fixed (CR-2): `_propagate_sentences` → `_deduplicate_nodes`. Added `write_dialog_records_incremental`.
- **Phase 3+4** (`add_records.py` + `db.py`): score tree → targeted DB upsert. New DB methods: `get_existing_path_signatures`, `get_existing_script_ids`, `upsert_nodes`, `upsert_sentences`, `update_sentence_scores`, `upsert_taxonomy_keywords`, `dedup_taxonomy_keywords`, `create_taxonomy_unique_index` (MD5 hash natural key). Embed only new sentences; recompute scores only for affected existing sentences.
- **Phase 5**: taxonomy keyword upsert via `db.upsert_taxonomy_keywords` (replaces broken inline insert in `score_tree.py`).
- **Post-success hook**: append `new_data.jsonl` records to `matched_data.jsonl`.

**Verified result**: 103→105 records, 1384→1395 tree nodes, 11 new DB sentences, 0 taxonomy duplicate groups.

### Commit 2 — `7904b89`: orphan sentence cleanup (crash recovery)

After DB upsert, delete sentences for new `call_id`s that exist in DB but not in the final tree. These orphans arise from partial runs where LLM merge decisions differed. Added `db.delete_sentences()`.

### Commit 3 — `7474552`: merge decisions cache persistence

`merge_dialogs` loaded but never saved the merge cache. Added `_save_merge_cache` call so LLM merge decisions for new records persist to `merge_decisions.json` for reproducibility.

### Note on ADR-034

This branch was based on main before the ADR-034 empty-pool descend fix landed. After merge, ADR-034 (`_has_reachable_sentences` in `retrieval_engine.py`), `diff.md`, and LL-007 remain in place — the descend fix is preserved.
