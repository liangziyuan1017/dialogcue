---
id: LL-008
title: Inline/stripped build skips final transforms → duplicate script_ids
doc_kind: lesson
feature_ids: [F004]
topics: [tree-transforms, dedup, script_id, build-pipeline, notebook]
status: accepted
created: 2026-07-17
schema_version: 1
trigger: build_tree_and_db.run_build_tree, add_dialog_to_tree, _dedup_script_ids_global
---

# LL-008: Inline/Stripped Build Skips Final Transforms → Duplicate script_ids

## Pitfall

A notebook or script that copies the body of `run_build_tree` but **strips the
`bdt.write_decision_tree(...)` call** (replacing it with an inline `add_dialog_to_tree`
loop + partial transforms) silently skips the final transform sequence —
`_deduplicate_nodes`, `_enforce_end_leaves`, `_consolidate_endpoints`,
`_dedup_script_ids_global`, `_sort_keywords`. The produced tree then contains:

1. **End-node mirror** — `normal_end`/`abrupt_end` with cloned dialog subtrees as
   children (registry re-parenting appends one node under multiple parents). Every
   `script_id` appears twice: once at the real path, once under `.../normal_end/...`.
2. **Cross-node real dups** — distinct node objects holding the same `script_id`
   (same turn placed in multiple branch nodes across passes).

Symptom: `check_script_ids_unique` reports thousands of duplicate `script_id`s even
though the codebase pipeline (`write_decision_tree`) is correct.

## Root Cause

The dedup/leaf transforms live **only inside `write_decision_tree` / `build_tree` /
`merge_dialogs`**. An inline build that calls `add_dialog_to_tree` directly never
invokes them. A stale kernel (module cached before the transforms were added) makes
even `bdt.write_decision_tree` run the old code. The codebase fix is invisible to the
notebook because the notebook bypasses the pipeline.

## Fix

- **Codebase**: `_dedup_script_ids_global` (global `script_id` uniqueness pass) wired
  into all three build entry points after `_consolidate_endpoints` (ADR-042).
- **`run_build_tree`** (build_tree_and_db.py): added a **defensive verify+repair tail**
  — after writing and re-loading the tree, count duplicate `script_id`s; if any, run
  `_dedup_script_ids_global` and re-write. No-op when the module is current; repairs
  when a stale/partial build wrote dups.
- **Notebook**: call `run_build_tree(rewarded)` or `bdt.write_decision_tree(...)` — do
  not strip the pipeline. Restart the kernel after codebase edits so the cached module
  is refreshed.

## Guard

- Any build path that calls `add_dialog_to_tree` must end with the full transform
  sequence (`_propagate_facts` → `_deduplicate_nodes` → `_enforce_end_leaves` →
  `_prune_empty_subtrees` → `_consolidate_endpoints` → `_dedup_script_ids_global` →
  `_sort_keywords`), in that order.
- After editing `tree_transforms.py` / `build_decision_tree.py`, restart the kernel or
  `importlib.reload(bdt)` — a cached module will silently run the old transforms.
- `TestF004ScriptIdUniqueness::test_all_script_ids_unique` is the hard invariant; a
  green run proves the full pipeline executed.

## Resolution (2026-07-17)

Verified end-to-end: `_dedup_script_ids_global` run manually on a loaded tree reduces
real dups to 0. Defensive tail added to `run_build_tree`. ADR-042 documents the
transform and its ADR-021 (DAG sharing) / ADR-023 (within-pool dedup) compatibility.
