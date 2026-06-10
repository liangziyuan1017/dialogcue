---
id: LL-001
title: "Schema alignment dropped prior feature state labels"
doc_kind: lesson
feature_ids: [F001]
topics: [schema, data-continuity, review]
status: draft
created: 2026-06-10
schema_version: 1
pitfall: "F001 built turns_annotated from raw output_manual.py only, dropping 493 state labels from F000 output_labeled.py"
root_cause: "Implementation only referenced output_manual.py; no check for intermediate outputs from prior features in dependency chain"
trigger_conditions: "When feature Fn depends on F(n-1) and F(n-1) produced intermediate output with annotations, but spec only references raw data source"
fix: "Modified build_turns_annotated() to load output_labeled.py and carry state dict into each turn"
guard: "Before implementing Fn with depends_on F(n-1), audit src/ for intermediate outputs from F(n-1) to carry forward; test: test_state_labels_from_output_labeled_carried_into_turns_annotated"
source_anchor: ["F001 review feedback", "src/output_labeled.py", "docs/features/F001-data-schema-alignment.md"]
---

# Schema Alignment Dropped Prior Feature State Labels

## Pitfall

F001 Data Schema Alignment built `turns_annotated` from raw `output_manual.py` only, dropping the 493 state labels already produced by F000 in `output_labeled.py`.

## Root Cause

The implementation plan and initial code only referenced `output_manual.py` as input. No check was made for intermediate outputs from prior features in the dependency chain (F000 → F001). The spec said "derive turns_annotated" without explicitly stating "include existing labels."

## Trigger Conditions

When a feature Fn depends on F(n-1) and F(n-1) produces an intermediate output file with annotations/labels that should be carried forward, but the spec only references the original raw data source.

## Fix

Modified `build_turns_annotated()` to accept `labeled_dialog` parameter. `align_all()` now loads `output_labeled.py` via `_load_output_labeled()` and passes labeled turns to `build_turns_annotated()`. Each turn in `turns_annotated` includes `state` dict if present in the labeled source.

## Guard

Before implementing any feature Fn that `depends_on: F(n-1)`, check if F(n-1) has produced output files in `src/` that contain annotations, labels, or derived data. If so, include those as input to Fn's alignment/transformation step. Test: `test_state_labels_from_output_labeled_carried_into_turns_annotated`.

## Source Anchors

- F001 review feedback: "include the state labels generated during f000 as well, check output_labeled.py"
- `src/output_labeled.py` — 493/805 turns with state labels
- `docs/features/F001-data-schema-alignment.md` — Review Notes section

## Prevention Notes

- Always audit `src/` for intermediate outputs from dependency features before writing alignment code
- Add a checklist item to writing-plans: "Check for prior feature outputs to carry forward"
- ADR-002 records this decision for future reference
