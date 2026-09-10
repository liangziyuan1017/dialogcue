---
REMOVED_FIELD_id: ADR-037
title: "Orphan sentence cleanup for crash recovery"
doc_kind: decision
feature_ids: [F015, F007]
topics: [incremental, database, crash-recovery, consistency]
status: accepted
created: 2026-07-09
updated: 2026-07-09
schema_version: 1
---

# Orphan Sentence Cleanup for Crash Recovery

## What

After the targeted DB upsert, delete sentences for new `call_id`s that exist in the DB but are absent from the final tree. These are orphans left by partial/crashed runs where LLM merge decisions differed between runs.

## Why

- If a previous incremental run inserted sentences for a new `call_id` but crashed before the tree stabilized (or merge decisions changed on retry), the DB holds sentences that no tree node references.
- Leaving orphans pollutes retrieval pools: `/recommend` could return a sentence whose `node_id` no longer matches the current tree structure.
- The tree is the source of truth for which sentences should exist; the DB must be a subset of the tree's sentences for the new `call_id`s.

## Decision

In `_phase3_4_score_db`, after upsert:
1. Collect `tree_script_ids` = sentences in the scored tree whose `source_call_ids` intersect the new `call_id`s.
2. Collect `db_script_ids` = existing DB `script_id`s containing any new `call_id`, plus newly inserted ones.
3. `orphans = db_script_ids - tree_script_ids`; `db.delete_sentences(orphans)`.

## Impact

| Component | Change |
|-----------|--------|
| `src/f007_infrastructure/db.py` | add `delete_sentences(script_ids)` |
| `src/add_records.py` | orphan diff + delete after upsert |

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Trust upsert, never delete | Orphans from prior crashed runs persist and corrupt retrieval |
| Rebuild sentences table from tree every append | Wasteful; deletes/re-inserts unaffected sentences |
