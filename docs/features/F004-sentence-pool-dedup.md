---
id: F004-dedup
parent: F004
name: Sentence Pool Deduplication in Tree Transforms
status: complete
owner: agent
created: 2026-06-23
updated: 2026-06-23
---

# F004-dedup: Sentence Pool Deduplication in Tree Transforms

## Why

The decision tree scored JSON contains duplicate `script_text` entries within single `sentence_pool` arrays. This causes the tree UI to show the same sentence twice, and wastes retrieval engine compute by scoring and ranking duplicates.

Root cause: three tree transform steps use `.extend()` / `.append()` without dedup after `_propagate_sentences` has already copied parent sentences into children:

1. **`_collapse_redundant_facts`** (tree_transforms.py:348) — `parent_sentences.extend(child_sentences)` when child contains propagated copies of parent's own sentences → parent gets `[A, B, A, B]`
2. **`_deduplicate_nodes`** (tree_transforms.py:281) — `.extend()` merges sibling pools without checking overlap
3. **`_consolidate_endpoints`** (tree_transforms.py:65) — walks entire tree collecting ending sentences, re-collecting propagated copies

## What

Add deduplication at each of the three high-risk transform steps so that `sentence_pool` arrays never contain duplicate `script_text` entries after the pipeline completes.

### Acceptance Criteria

- [x] `_collapse_redundant_facts` deduplicates when extending parent pool from collapsed child
- [x] `_deduplicate_nodes` deduplicates when merging sibling sentence pools
- [x] `_consolidate_endpoints` deduplicates when collecting ending sentences into normal_end
- [x] Regenerated `decision_tree_scored.json` has zero duplicate `script_text` within any single `sentence_pool`
- [x] Existing tests pass
- [x] New tests verify dedup behavior at each transform step

## Scope

- Files: `src/f004_decision_tree/tree_transforms.py`, `src/f004_decision_tree/tests/`
- No changes to tree structure, branching logic, or scoring
- UI dedup (already applied in `tree_explorer_ui.js`) remains as defense-in-depth

## Dependencies

- F004 (parent)

## Resolution (2026-07-16)

Root cause fully addressed: `_propagate_sentences` removed from `build_tree` (last caller; production `write_decision_tree` never used it), and `_collect_tree_sentences` (`score_tree.py`) now dedups the walk by `node_id` so deep-copied DAG subtrees are counted/embedded once. The within-pool `_dedup_pool` guards from this feature remain as defense-in-depth.
