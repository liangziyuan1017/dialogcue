---
id: ADR-016
title: Fact-by-Fact Tree Walking Eliminates Composite Nodes
status: accepted
created: 2026-06-17
updated: 2026-06-17
decision_type: architecture
feature_ids: [F004]
---

# ADR-016: Fact-by-Fact Tree Walking Eliminates Composite Nodes

## Context

Segments from `_extract_segments` could have composite branch keys like `{'facts': ['ability_to_pay', 'financial_hardship'], 'emotions': ['difficulty']}`. The original `build_tree` tried to match the entire composite as a single node, then `_split_composite_nodes` post-processed to break them apart. This created intermediate composite nodes and required a separate splitting pass. Some composites were missed (e.g. `f:financial_hardship|e:helplessness`), requiring iterative fixes.

## Decision

Walk each segment's facts and emotions one at a time in `build_tree`. For each fact, find or create a single-fact child node and advance `current_node`. For each emotion, find or create a single-emotion child and advance. Composites are never created in the first place.

## Why

- Eliminates an entire class of bugs (missed composites, partial splits)
- `_split_composite_nodes` becomes a no-op safety net
- Simpler mental model: every node has exactly one key dimension
- Matches the tree's actual structure (single-key nodes)

## Consequences

- `_split_composite_nodes` is retained but effectively does nothing on the current tree
- Tree depth increases slightly (more single-fact nodes in sequence)
- All branch keys are guaranteed to have at most one fact OR one emotion OR one action
