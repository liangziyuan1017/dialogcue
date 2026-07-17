---
id: ADR-045
title: "source_call_ids as sentence_sources join table"
doc_kind: decision
feature_ids: [F017]
topics: [scalability, database, schema, merge]
status: accepted
created: 2026-07-17
updated: 2026-07-17
schema_version: 1
---

# source_call_ids as sentence_sources Join Table

## What

Replace the unbounded `source_call_ids` list on sentence dicts with a `sentence_sources` join table: `CREATE TABLE sentence_sources (script_id TEXT, call_id TEXT, PRIMARY KEY (script_id, call_id))`. Merge operations query this table instead of doing list membership + append.

## Why

The current `source_call_ids` list on each sentence causes O(k²) merge costs: every placement checks `call_id in source_call_ids` (O(k) scan) and appends (O(1) amortized but O(k) copy). At 100k dialogs with ~2M turns, this is the single highest-leverage bottleneck (H1/M1 in the risk inventory).

A join table with `(script_id, call_id)` primary key makes membership check O(log n) via B-tree index and insert O(log n). Merge becomes O(new batch) instead of O(existing × new).

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep source_call_ids list with set() conversion | Still O(k) memory per sentence; set rebuild on every load; doesn't fix storage bloat |
| Store as JSON array in sentence row | No index; membership check is O(k); same problem in a different column |
| Separate call_ids table with FK | Extra join; same complexity as composite PK table |

## Impact

- New table: `sentence_sources (script_id TEXT, call_id TEXT, PRIMARY KEY (script_id, call_id))`
- `build_decision_tree._place_sentence` queries DB instead of list membership
- `tree_transforms` functions read from join table instead of `source_call_ids` list
- ADR-029 (additive tree building) merge logic updated to use join table queries
- ADR-035 (incremental append) merge step simplified — no more list append
