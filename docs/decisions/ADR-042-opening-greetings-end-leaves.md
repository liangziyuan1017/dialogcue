---
REMOVED_FIELD_id: ADR-042
title: Opening Node Pools Greetings, Precise Ending Gestures, End Nodes Are Leaves
status: accepted
created: 2026-07-16
updated: 2026-07-16
decision_type: architecture
feature_ids: [F004]
supersedes: [ADR-038]
---

# ADR-042: Opening Node Pools Greetings, Precise Ending Gestures, End Nodes Are Leaves

## Context

Three related bugs were producing duplicate `script_id` values and wrong `gesture_type`
tags in the decision tree. They were surfaced by `check_script_ids_unique` against a
production tree (6589 duplicated keys, 13604 occurrences) and by the
`TestF004OpeningGestures` invariant suite.

1. **Opening node spawned `a:greeting` children (ADR-038).** The root node
   (`role: "opening"`) ran the same action-splitting logic as decision nodes, so
   greeting sentences were placed under an `a:greeting` action child instead of the
   root `sentence_pool`, and no sentence was ever tagged `gesture_type: "opening"`.
   This contradicted the F004 feature spec (greetings are opening gestures in the root
   pool) and the `TestF004OpeningGestures` invariants.

2. **Closing block over-tagged gestures.** When a segment had `is_closing=True`, every
   sentence in that segment was stamped `gesture_type: "ending"` — including greetings
   and `plan_proposal` sentences that merely shared the segment because no customer
   turn produced a non-empty branch key to flush it. Greetings ended up tagged
   `"ending"`.

3. **End nodes had children (multi-parent DAG mirror).** `add_dialog_to_tree` re-parents
   registry nodes by an identity-only key `(facts, emotions, branch_key)` that does not
   include the path. When `matching = registry[identity]` already had a parent elsewhere,
   appending it to `current_node.children` created a node with two parents. The subtree
   under `normal_end` became a mirror of the real subtree under root, so every
   `script_id` appeared twice — once at `initial_contact/...` and once at
   `initial_contact/normal_end/...`. All 6589 dup keys were this different-node mirror;
   same-node dups were 0.

## Decision

Three changes in `src/f004_decision_tree/`:

1. **Opening node pools greetings (`build_decision_tree.py`, `_place_sentences_in_node`).**
   For `role == "opening"`, sentences are merged directly into the node's
   `sentence_pool`; sentences with `collector_action == "greeting"` are tagged
   `gesture_type: "opening"`. The opening node no longer spawns `a:greeting` /
   `a:information` action children. **Reverses ADR-038.**

2. **Precise ending gestures (`build_decision_tree.py`, closing block).** The closing
   segment loop now tags `gesture_type: "ending"` only on sentences whose
   `collector_action` is in `CLOSING_ACTIONS` (`closure`, `goodbye`), not on every
   sentence in the segment.

3. **End nodes are leaves (`tree_transforms.py`, `_enforce_end_leaves`).** A new
   transform clears `children` on every `normal_end` / `abrupt_end` node. It is wired
   into all three build entry points (`build_tree`, `merge_dialogs`,
   `write_decision_tree`) immediately after `_deduplicate_nodes`. This breaks the
   multi-parent mirror: the cloned subtree under `normal_end` is dropped, and those
   nodes remain reachable only via their real root path.

## Why

- The F004 feature spec defines the opening gesture as sentences in the root pool tagged
  `gesture_type: "opening"`; ADR-038 violated that spec and the invariant suite.
- `gesture_type` is a per-sentence property of the action that produced it, not of the
  segment it happened to be flushed in. Tagging a greeting `"ending"` because a later
  turn in the same segment was a `closure` was always wrong.
- `normal_end` / `abrupt_end` are terminal nodes by definition; they must not have
  dialog subtrees. The registry re-parenting is a useful DAG mechanism for decision
  nodes, but end nodes participating in it created the observable duplicate-`script_id`
  explosion. Forcing end nodes to leaves is the minimal fix that preserves the DAG
  sharing for decision nodes while eliminating the mirror.

## Consequences

- Root `sentence_pool` again contains greeting sentences with `gesture_type: "opening"`;
  root has no `a:greeting` child.
- `gesture_type: "ending"` appears only on `closure` / `goodbye` sentences.
- `normal_end` and `abrupt_end` have empty `children` after every build; the
  duplicate-`script_id` mirror is eliminated.
- `build_tree` now also calls `_deduplicate_nodes` (it previously skipped it, unlike
  `merge_dialogs` / `write_decision_tree`) for pipeline consistency.
- Tests updated: `test_additive.py::test_adds_greeting_to_root` now asserts no
  `a:greeting` child and opening gestures in root pool. The
  `TestF004OpeningGestures` suite passes.
- ADR-038 marked `superseded`.
- **Global `script_id` dedup (`_dedup_script_ids_global`)** runs as a final build pass
  after `_consolidate_endpoints`. It walks the tree once (DAG-safe via an `REMOVED_FIELD_id(node)`
  visited set) and keeps only the first occurrence of each `script_id`, dropping later
  ones. This eliminates cross-node duplicate `script_id`s that remain after the
  end-node fix — distinct node objects holding the same `script_id`, caused by a call
  being re-added or registry routing placing the same turn in multiple branch nodes.
  Complements ADR-023 (within-pool text dedup); no conflict with ADR-021 (node sharing
  preserved — only duplicate *sentences* are removed, shared nodes visited once).
  Enforced by `TestF004ScriptIdUniqueness::test_all_script_ids_unique`.

## Repair of existing trees

Existing production trees with the mirror can be repaired in place by stripping
children from end nodes — every mirrored node also lives under the real root path, so
no `script_id` is lost. See `fix_normal_end_mirror.py` (repo root) for a one-off repair
script that reports end-nodes-with-children, strips them, verifies no occurrences are
lost, and writes the fixed tree.
