---
id: LL-003
title: Propagate-then-extend creates silent duplicates
doc_kind: lesson
feature_ids: [F004]
topics: [tree-transforms, dedup, sentence-pool]
status: accepted
created: 2026-06-23
schema_version: 1
trigger: tree_transforms._collapse_redundant_facts, _deduplicate_nodes, _consolidate_endpoints
---

# LL-003: Propagate-then-Extend Creates Silent Duplicates

## Pitfall

When `_propagate_sentences` copies a parent's sentence pool into an empty child, and a later transform collapses or merges that child back into the parent (or sibling), the `.extend()` silently doubles the sentences. The duplicate is invisible in tree structure — it only appears as repeated `script_text` in the pool array.

## Root Cause

`_propagate_sentences` uses shallow copy (`list(parent_pool)`) to fill empty children. Transforms that aggregate pools (`_collapse_redundant_facts`, `_deduplicate_nodes`, `_consolidate_endpoints`) use bare `.extend()` without checking for overlap.

## Fix

Added `_dedup_pool()` after every `.extend()` in the three transforms. Keyed on `script_text`.

## Guard

Any future transform that merges sentence pools must call `_dedup_pool()` after the merge. Search for `.extend(` on `sentence_pool` as a code review trigger.
