---
id: ADR-023
title: Sentence pool deduplication at transform boundaries
status: accepted
date: 2026-06-23
related: [F004-dedup, ADR-018, ADR-021]
---

# ADR-023: Sentence Pool Deduplication at Transform Boundaries

## Context

Three tree transform steps (`_collapse_redundant_facts`, `_deduplicate_nodes`, `_consolidate_endpoints`) use `.extend()` / `.append()` to merge sentence pools without deduplication. After `_propagate_sentences` copies parent pools into empty children, subsequent transforms that aggregate pools back up create duplicate `script_text` entries — e.g., parent gets `[A, B, A, B]` after collapsing a child that received propagated copies.

## Decision

Add a `_dedup_pool(pool)` helper that deduplicates by `script_text` (keeping first occurrence). Call it immediately after every `.extend()` that merges sentence pools in the three transforms.

## Rationale

- Dedup at the source (transform boundaries) is more correct than dedup at display time (UI) — it fixes the data for all consumers (UI, retrieval engine, scoring).
- Using `script_text` as the dedup key is sufficient because two sentences with the same text but different metadata represent the same utterance and should not appear twice.
- Defense-in-depth: UI dedup (`tree_explorer_ui.js`) remains as a safety net.

## Consequences

- `_dedup_pool` is O(n) per call using a set — negligible cost vs tree building.
- If two sentences with identical text but genuinely different scoring profiles exist, only the first is kept. In practice this does not occur because scoring is deterministic per script_text.
