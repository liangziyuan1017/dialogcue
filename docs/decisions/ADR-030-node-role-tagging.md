# ADR-030: Node Role Tagging

**Date:** 2026-07-07
**Status:** Accepted

## Context

`_split_by_action` used shape-based role inference: any non-fact/emotion node with >1 distinct `collector_action` got action-split. Root and `normal_end` matched this shape, causing opening greetings to leave root and ending sentences to scatter.

## Decision

Tag every node with `role ∈ {"opening", "ending", "decision", "action"}` at creation time. All transforms and inserters check `role` and skip non-applicable nodes:

- Root: `role="opening"` — never action-split
- End nodes: `role="ending"` — never action-split
- Fact/emotion children: `role="decision"` — eligible for action split
- Action children: `role="action"` — leaf-level, not split further

## Consequences

- Prevents `_split_by_action` from corrupting root and end nodes
- Self-documenting: node purpose is explicit, not inferred from shape
- Invariant testable: every node has a valid role
