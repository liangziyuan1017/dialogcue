---
id: ADR-002
title: "F001 carry F000 state labels into turns_annotated"
doc_kind: decision
feature_ids: [F001]
topics: [schema, state-labels, continuity]
status: accepted
created: 2026-06-10
updated: 2026-06-10
schema_version: 1
---

# F001 Carry F000 State Labels into turns_annotated

## What

Include the `state` dict from `output_labeled.py` (F000 output) in each turn of `turns_annotated`. Turns with labels carry `state` with keys `facts`, `emotions`, `willingness` (customer) or `action` (collector). Turns without labels omit `state`.

## Why

F000 already labeled 493/805 turns with state keywords. F002 will extend labeling to all turns. If F001 drops these labels, F002 must re-derive them — wasting the F000 work and breaking the data lineage chain. The aligned schema should be a superset of prior outputs, not a lossy transformation.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Drop labels, let F002 re-derive | Wastes F000 work; breaks data continuity; F002 may produce different labels |
| Only include labels for fully-annotated turns | Partial labels are still valid — F002 will extend, not replace |
| Store labels in separate file | Violates SOP schema: `turns_annotated` must be self-contained per record |
