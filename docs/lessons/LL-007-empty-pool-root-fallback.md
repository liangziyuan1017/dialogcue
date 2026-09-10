---
REMOVED_FIELD_id: LL-007
title: "Empty sentence_pool on intermediate nodes causes root fallback"
doc_kind: lesson
feature_ids: [F006]
topics: [retrieval, decision-tree, fallback, sentence-pool]
status: accepted
created: 2026-07-09
schema_version: 1
pitfall: "Intermediate tree nodes have empty sentence_pool (sentences live in children). _find_matching_nodes_subset skipped these nodes and fell back to root, always returning the same sentence."
root_cause: "aggregate_pools(nodes) was the sole validity check for a node match. It only checks the node's own sentence_pool, not descendant sentences. 23 of 32 single-label nodes have empty pools."
trigger_conditions: "When the decision tree has intermediate nodes with sentence_pool=[] but children with sentences, and _find_matching_nodes_subset is used for node matching"
fix: "Added _has_reachable_sentences(nodes) that calls descend_for_sentences to check children. Replaced aggregate_pools checks in 3 locations: exact match, subset match, root fallback. In subset match, also resolved the pool from descend_for_sentences when own pool is empty."
guard: "test_anxiety_node_returned_not_root, test_personal_info_node_returned_not_root, test_income_loss_node_returned_not_root in TestDescendIntoChildrenForPool"
source_anchor: ["src/f006_retrieval_engine/retrieval_engine.py:82-84", "src/f006_retrieval_engine/retrieval_engine.py:98", "src/f006_retrieval_engine/retrieval_engine.py:140-143", "src/f006_retrieval_engine/retrieval_engine.py:155", "docs/decisions/ADR-034-descend-for-sentences-on-empty-pool.md"]
---

# Empty sentence_pool on intermediate nodes causes root fallback

## Pitfall

The `/recommend` API always returned the same sentence regardless of input. Only `state_tags` varied because extraction worked correctly, but node matching always fell back to root.

## Root Cause

`_find_matching_nodes_subset()` used `aggregate_pools(nodes)` as the sole check for whether a node match was valid. This function only checks a node's own `sentence_pool`. In the decision tree, 23 of 32 single-label nodes have `sentence_pool=[]` — their sentences live in child/leaf nodes. When these nodes matched, the function skipped them and continued dropping labels until it hit root (`initial_contact`, 308 sentences), which always ranked the same top sentence.

## Fix

Added `_has_reachable_sentences(nodes)` that delegates to `descend_for_sentences(nodes)` to check both own pool and descendant pools (up to 4 levels). Replaced `aggregate_pools` checks in three locations within `_find_matching_nodes_subset`. In the subset match path, also resolved the pool from `descend_for_sentences` when the own pool is empty, avoiding a second call.

## Guard

Three tests in `TestDescendIntoChildrenForPool` verify that `anxiety`, `personal_info`, and `income_loss` nodes are returned directly (not root) with no `root_fallback` in fallbacks.
