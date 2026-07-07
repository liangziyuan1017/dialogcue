# ADR-029: Additive Tree Building

**Date:** 2026-07-07
**Status:** Accepted
**Supersedes:** ADR-015, ADR-017, ADR-018, ADR-022, ADR-023

## Context

The original tree construction pipeline built a raw tree then applied 6 global post-transform passes (`_split_composite_nodes`, `_merge_sibling_facts`, `_collapse_redundant_facts`, `_split_by_action`, `_propagate_facts`, `_deduplicate_nodes`). This "place-then-move" approach caused bugs: `_split_by_action` corrupted root (scattered opening greetings) and end nodes (re-scattered ending sentences). Global transforms also prevented incremental updates — any new data required a full rebuild.

## Decision

Replace the global post-transform chain with **additive per-dialog insertion** via `add_dialog_to_tree(tree, record, registry)`. Each conversation is placed in its final home at insert time:

- Greeting turns → root.sentence_pool (never moved)
- Action split at insert (scoped to decision nodes only)
- Closing sentences → normal_end.sentence_pool (never placed in decision nodes)
- Redundant-fact skip at insert (if fact already in accumulated_facts)
- Sibling dedup via node_registry

`merge_dialogs(tree_path, new_records)` provides incremental merge: load existing tree, add new records, save. Full rebuild = delete tree file + merge all.

## Consequences

- Eliminates the `_split_by_action` bug class (root/end corruption)
- Enables incremental rebuild for new data (Scaling Path)
- Simpler code: no 6-transform chain to maintain
- Idempotent: inserting the same record twice produces the same tree
- Trade-off: cross-dialog dedup is myopic (each insert only sees current tree state); `_deduplicate_nodes` kept as a final pass for safety
