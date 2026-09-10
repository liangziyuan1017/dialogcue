---
REMOVED_FIELD_id: ADR-018
title: Redundant Fact Collapse with Inherited Facts Propagation
status: superseded
created: 2026-06-17
updated: 2026-06-23
decision_type: architecture
feature_ids: [F004]
superseded_by: ADR-022
---

# ADR-018: Redundant Fact Collapse with Inherited Facts Propagation

## Context

With local tree building (ADR-015), the same fact can appear as separate nodes under different parents. But when a customer restates a fact already established earlier in the conversation (e.g., mentions `financial_hardship` again after already being on a `f:financial_hardship` branch), the tree creates a redundant fact node. This produces paths like `f:financial_hardship → f:financial_hardship` where the second node adds no information.

## Decision

Two post-processing steps:

1. **`_propagate_facts`** — walks the tree top-down, accumulating facts from the parent chain into each node's `inherited_facts` field. Also propagates `fact_context` onto each sentence entry. A node's own `branch_key.facts` are NOT included in its `inherited_facts` (strict separation).

2. **`_collapse_redundant_facts`** — iteratively removes fact nodes whose facts are already in the accumulated parent facts (own facts ⊆ parent facts). Their sentences are promoted to the parent's pool and their children become parent's children. Uses fixed-point iteration to handle cascading collapses.

## Why

- Eliminates redundant branches where a fact is restated (common in real conversations)
- `inherited_facts` enables efficient redundancy detection without parent traversal
- `fact_context` on sentences provides the full fact context for each script
- Fixed-point iteration handles chains of redundant nodes (A→B→C where all are redundant)
- Strict `inherited_facts` (no self-inclusion) makes the field semantically correct

## Consequences

- Tree has fewer redundant nodes after collapse
- Every node has `inherited_facts` list (possibly empty for root)
- Every sentence entry has `fact_context` list
- Collapse is iterative — may require multiple passes for cascading redundancies
- Pipeline order: `_split_composite_nodes → _merge_sibling_facts → _collapse_redundant_facts → _split_by_action → _propagate_facts`

## Supersession

ADR-022 extends this to also collapse redundant **emotion** nodes (e.g., `anger → anger`), tracking `accumulated_emotions` in addition to `accumulated_facts`. The function name `_collapse_redundant_facts` is unchanged but now handles both facts and emotions.
