---
id: ADR-038
title: Opening Node Spawns Action Children for Greeting and Information
status: accepted
created: 2026-07-10
updated: 2026-07-10
decision_type: architecture
feature_ids: [F004]
---

# ADR-038: Opening Node Spawns Action Children for Greeting and Information

## Context

The root node (`state_id: "initial_contact"`, `role: "opening"`) pooled greeting and information sentences directly into its `sentence_pool` instead of creating `a:greeting` / `a:information` action child nodes. This caused three problems:

1. **Tree UI**: Dialogs like dialog 35 that start with collector greetings and information before the first customer branch key showed no greeting/information nodes in the traced path. The trace logic (`findChildByAction(root, "greeting")`) found no matching child, so early turns mapped to nothing.
2. **Structural inconsistency**: Decision nodes at depth ≥ 1 spawned `a:<action>` children via `_place_sentences_in_node`, but the opening node did not — it short-circuited with an early return that pooled all sentences.
3. **Lost navigability**: Greetings were extracted in a separate pre-loop (`add_dialog_to_tree` lines 260-270) and skipped in segment processing (`_extract_segments` line 455-456: `if action == "greeting": continue`), bypassing the normal action-child creation path entirely.

## Decision

**The opening node uses the same action-splitting logic as decision nodes.** Three changes in `build_decision_tree.py`:

1. **`_place_sentences_in_node`**: Removed the `role == "opening"` early-return block. Changed `if role != "decision"` to `if role not in ("decision", "opening")` so opening nodes fall through to the action-splitting logic (group by `collector_action` → create `a:<action>` children).

2. **`add_dialog_to_tree`**: Removed the separate greeting extraction loop (lines 260-270) that pooled greetings into root's `sentence_pool`. Greetings now flow through normal segment processing.

3. **`_extract_segments`**: Removed `if action == "greeting": continue` so greetings are included in segment sentences with `collector_action: "greeting"`.

## Why

- Greeting and information are collector actions that occur before the first customer branch key — they belong as action children under root, not pooled into root's sentence pool
- The trace logic (`findChildByAction`) only looks at child nodes, not sentence pools — pooling made these turns invisible in the UI
- Decision nodes already had this behavior; the opening node was an inconsistency
- No server-side trace changes needed — `findChildByAction(root, "greeting")` now finds the `a:greeting` child

## Consequences

- Root node now has `a:greeting` (106 sentences), `a:information` (120 sentences), and other action children alongside `normal_end` and `abrupt_end`
- Root's `sentence_pool` no longer contains greeting/information sentences (only unassigned sentences with no `collector_action`)
- Tree rebuilt: 1403 nodes (was 1384)
- `_prune_empty_subtrees` never prunes action nodes (`role == "action"` returns False) — new children survive
- `_deduplicate_nodes` merges duplicate `a:greeting` children by identity — correct
- `_consolidate_endpoints` only strips/re-adds `normal_end`/`abrupt_end` — action children untouched
- Test `test_adds_greeting_to_root` updated to assert `a:greeting` child exists instead of root pool containing `gesture_type: "opening"`
