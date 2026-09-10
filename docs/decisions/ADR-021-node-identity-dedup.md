---
REMOVED_FIELD_id: ADR-021
title: Node Identity-Based Deduplication with DAG Support
status: accepted
created: 2026-06-23
updated: 2026-06-23
decision_type: architecture
feature_ids: [F004]
---

# ADR-021: Node Identity-Based Deduplication with DAG Support

## Context

After all tree transforms (split composite, merge siblings, collapse redundant, split by action), the tree could contain nodes at different positions that represent the same semantic state — same accumulated facts, same accumulated emotions, same branch key. These appeared as duplicate nodes in the UI, confusing users.

The previous dedup only checked sibling `branch_key` equality, missing duplicates at different depths or under different parents. Additionally, the identity `(inherited_facts, branch_key)` ignored emotions in the parent path, so nodes reached via different emotion paths (e.g., `anger → propose` vs `anxious → propose`) were incorrectly merged.

## Decision

**Node identity = `(inherited_facts, inherited_emotions, branch_key)`. Two nodes with the same identity are the same semantic state and must be one node.**

Three mechanisms enforce this:

1. **Registry check during `build_tree()`** — Before creating a new child node, compute its identity from the current `accumulated_facts` and `accumulated_emotions`. If a node with that identity already exists in a global `node_registry`, reuse it. Add it as a child of the current parent (creating a DAG). Cycle prevention: if the matched node is an ancestor of the current node, skip reuse and navigate to it without modifying the tree structure.

2. **`_propagate_facts` extended** — Now also computes `inherited_emotions` (accumulated emotions from root to parent) and `node_id` (SHA-256 hash of the identity tuple, 12-char hex). Every node gets `inherited_facts`, `inherited_emotions`, and `node_id`.

3. **`_deduplicate_nodes` post-transform** — After all transforms and propagation, merges sibling nodes with the same identity (combines sentence_pools and children). Safety net for duplicates created by transforms.

### DAG Handling

The tree is now a DAG — a node can appear under multiple parents. All recursive tree-walking functions use `_visited` sets (by `REMOVED_FIELD_id(node)`) to prevent infinite recursion. The UI uses `node_id` as the Cytoscape node ID, so duplicate references render as a single node with multiple incoming edges.

### Cycle Prevention

`_is_ancestor(matching, current_node)` checks if reusing a registry node would create a cycle. If so, the node is navigated to without being added as a child (the fact/emotion is already inherited).

## Why

- `(inherited_facts, branch_key)` alone merges nodes reached via different emotion paths — wrong
- `(inherited_facts, inherited_emotions, branch_key)` captures the full semantic context
- Registry check prevents most duplicates at creation time; post-transform dedup catches the rest
- Cycle prevention is necessary because records can revisit the same fact/emotion later in the conversation
- DAG is the correct structure when multiple paths converge to the same state

## Consequences

- Tree is a DAG, not strictly a tree — a node can have multiple parents
- Every node has `node_id`, `inherited_facts`, `inherited_emotions`
- UI renders DAG correctly: shared nodes appear once with multiple incoming edges
- All recursive walkers have `_visited` cycle protection
- `_count_nodes` uses visited set to avoid double-counting
- 9 non-sibling duplicates remain as DAG shared nodes (correct behavior)
- Pipeline order: `build_tree (with registry) → transforms → _propagate_facts (with emotions) → _deduplicate_nodes`
