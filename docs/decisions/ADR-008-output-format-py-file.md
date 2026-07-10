---
id: ADR-008
title: "F001 output format: .py file with results list"
doc_kind: decision
feature_ids: [F001]
topics: [schema, output-format, serialization]
status: accepted
created: 2026-06-10
updated: 2026-06-10
schema_version: 1
---

# F001 Output Format: .py File with Results List

## What

Write aligned output to `src/f001_schema_alignment/data/output_aligned.py` as `results = [...]` — a Python file with a top-level list variable, matching the format of `src/f000_keyword_discovery/data/output_labeled.py`.

## Why

Consistency with existing data pipeline. All intermediate outputs (`output_labeled.py`, `output_aligned.py`, `output_rewarded.py`) use this format. Downstream scripts load them via `importlib`. Switching to JSON would break the loading pattern and require changes across F003–F006.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| JSON output | Breaks `importlib` loading pattern used by all downstream features |
| CSV output | Loses nested structure (dialog, context dict); no type fidelity |
| PostgreSQL (F007 target) | Correct for 10K scale, but premature for 108-record prototype |
