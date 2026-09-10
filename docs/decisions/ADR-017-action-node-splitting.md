---
REMOVED_FIELD_id: ADR-017
title: Action Node Splitting Ensures Uniform Sentence Placement
status: accepted
created: 2026-06-17
updated: 2026-06-17
decision_type: architecture
feature_ids: [F004]
---

# ADR-017: Action Node Splitting Ensures Uniform Sentence Placement

## Context

After fact-by-fact walking and composite splitting, sentence pools at fact/emotion nodes could contain sentences with different `collector_action` values (e.g., both "information" and "pressure" sentences at the same node). This made the tree structure inconsistent: some sentences lived directly in fact/emotion node pools, while others were under action child nodes. The UI couldn't reliably determine where to find sentences for a given action type.

## Decision

`_split_by_action` force-splits sentence pools into action child nodes (`a:xxx`) for any node that has facts or emotions in its branch key. Each action becomes a separate child node with its own sentence pool. Sentences without `collector_action` remain in the parent node's pool. Nodes without facts/emotions keep their sentences in-place.

The tree structure becomes uniform: `fact → emotion → action → sentences`. Every sentence with a `collector_action` lives under an action node. Sentences without an action label stay in the parent context pool.

## Why

- Uniform structure: UI can always find sentences under action child nodes for fact/emotion parents
- Action-level filtering: selecting a specific action type is a tree traversal, not a pool scan
- Matches the mental model: the collector chooses an action, then selects from action-specific scripts
- No mixed pools: eliminates ambiguity about which sentences belong to which action

## Consequences

- Tree has more nodes (action nodes interleaved between fact/emotion and sentences)
- Action nodes use `branch_key: {"action": "xxx"}` and `state_id: "a:xxx"`
- Nodes without facts/emotions (e.g., root) keep sentences in their own pool
- `_split_by_action` runs after `_collapse_redundant_facts` in the pipeline
