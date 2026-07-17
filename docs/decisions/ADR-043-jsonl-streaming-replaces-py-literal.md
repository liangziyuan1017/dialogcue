---
id: ADR-043
title: "Replace .py literal result files with streaming JSONL"
doc_kind: decision
feature_ids: [F017]
topics: [scalability, streaming, serialization, output-format]
status: accepted
created: 2026-07-17
updated: 2026-07-17
schema_version: 1
supersedes: [ADR-008]
---

# Replace .py Literal Result Files with Streaming JSONL

## What

Replace all `results = [...]` Python-literal output files (`output_labeled.py`, `output_aligned.py`, `output_rewarded.py`) with JSONL format. Downstream consumers change `_load_py_results(path)` → `load_jsonl(path)` returning the same `list[dict]` API. A one-time `convert_py_to_jsonl.py` migration script converts existing files.

## Why

The `.py` literal format (ADR-008) loads the entire corpus into RAM via `importlib` exec. At 100k dialogs this is ~1.5 GB per load, with multiple stages each loading independently. JSONL allows line-by-line streaming, bounding memory to O(batch_size) instead of O(corpus).

ADR-008 explicitly noted that PostgreSQL was "correct for 10K scale, but premature for 108-record prototype." F017 is the natural evolution now that the corpus is scaling to 100k.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep .py literal format | OOM at 100k; ~1.5 GB per load; multiple stages multiply the problem |
| SQLite for pipeline outputs | Adds query engine complexity for sequential access that JSONL handles simply |
| PostgreSQL for all intermediate outputs | Network round-trip overhead for sequential pipeline stages; DB is for served data (Track 2) |
| CSV | Loses nested structure (dialog, context dict); no type fidelity |

## Impact

- One-time migration: `src/scripts/convert_py_to_jsonl.py` converts existing `.py` files to `.jsonl`
- All `_load_py_results` / importlib exec calls replaced with `load_jsonl`
- `add_records.py` (ADR-035) append logic changes from "load .py + append + rewrite .py" to "append JSONL lines"
- ADR-008 superseded
