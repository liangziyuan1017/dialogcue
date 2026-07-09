---
id: ADR-034
title: Descend into children when node sentence_pool is empty
status: accepted
created: 2026-07-09
updated: 2026-07-09
decision_type: bug-fix
feature_ids: [F006]
---

# ADR-034: Descend into children when node sentence_pool is empty

## Context

The `/recommend` API always returned the same sentence regardless of input, with only `state_tags` varying. Root cause: `_find_matching_nodes_subset()` used `aggregate_pools(nodes)` as the sole validity check for a node match. When a node's own `sentence_pool` was empty (sentences lived in child/leaf nodes), the function skipped the node and continued dropping labels until it hit the root node (`initial_contact`, 308 sentences). The ranking then picked the same top sentence from the root pool every time.

23 of 32 single-label nodes in the decision tree have empty `sentence_pool` — their sentences are in children.

## Decision

When a matched node's own `sentence_pool` is empty, call `descend_for_sentences(nodes)` to walk children (up to `find_node_max_levels=4`) before skipping to the next subset or root fallback.

Three fix points in `_find_matching_nodes_subset`:
1. **Exact match** (line 91-94): replace `aggregate_pools(nodes)` check with `_has_reachable_sentences(nodes)`
2. **Subset match** (line 135-143): try `descend_for_sentences` when `aggregate_pools` returns empty
3. **Root fallback** (line 147-148): replace `aggregate_pools(root_nodes)` with `_has_reachable_sentences(root_nodes)`

Added helper `_has_reachable_sentences(nodes)` which delegates to `descend_for_sentences`.

## Consequences

- Nodes with empty pools but child sentences are now valid matches (e.g. `anxiety` → confidence 0.95 with `descend` fallback, instead of root fallback at 0.2)
- Root fallback only triggers when no label combination matches AND no descendants have sentences
- No change to `recommend()` — it already calls `descend_for_sentences` as a last resort; the fix ensures correct nodes reach that point
- Performance: `descend_for_sentences` only runs when `aggregate_pools` returns empty (minority case), walks max 4 levels
