---
REMOVED_FIELD_id: ADR-015
title: Local Tree Building Without Global Node Reuse
status: accepted
created: 2026-06-17
updated: 2026-06-17
decision_type: architecture
feature_ids: [F004]
---

# ADR-015: Local Tree Building Without Global Node Reuse

## Context

`build_tree` originally used `_find_node_by_branch_key(root, branch_key)` to search the entire tree for an existing node with the same branch key when a direct child match wasn't found. This global reuse meant that a fact like `financial_hardship` appearing in different conversation paths would merge into a single node, breaking path continuity. The dialog tracer couldn't navigate from one path to another because the shared node had children from multiple unrelated paths.

## Decision

Remove global node search. Each segment's branch key is matched only against children of `current_node`. If no match, create a new child. This means the same fact/emotion can appear as separate nodes under different parents, preserving each record's conversation path as a connected subtree.

## Why

- Path continuity: every record's conversation is a walkable path from root
- Dialog tracer works correctly: it follows parent→child edges without jumps
- No hidden cross-path connections that don't exist in real conversations
- `_merge_sibling_facts` and `_collapse_redundant_facts` handle dedup as post-processing

## Consequences

- Same fact can appear as multiple nodes (e.g. `f:financial_hardship` under 7 different parents)
- Tree is larger (383 nodes vs 157 before global reuse removal)
- Post-processing steps handle merging/collapsing where appropriate
- All 31 records have navigable paths through the tree
