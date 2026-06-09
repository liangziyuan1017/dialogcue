---
name: memory-prune
description: >
  Prune, merge, or deprecate stale durable memory without destructive deletion.
  Use when: duplicate, stale, or invalidated knowledge should be compacted safely.
  Not for: deleting active knowledge or rewriting project history without audit.
  Output: a prune report with non-destructive lifecycle actions.
triggers:
  - "prune memory"
  - "reduce entropy"
  - "clean up knowledge"
  - "stale docs"
  - "merge decisions"
  - "deprecate"
---

# Memory Prune

Route non-destructive knowledge cleanup requests to the memory-prune workflow.

## What this skill does

1. Confirms the task is about lifecycle cleanup rather than raw deletion
2. Routes entropy-reduction work to the memory-prune workflow
3. Keeps pruning separate from indexing, retrieval, and decision capture

## When to use

- Durable knowledge is stale, duplicated, or invalidated
- A safe merge or deprecation review is needed

## When NOT to use

- The task is to destroy knowledge without audit
- The task is to create new memory artifacts

## Execution

→ Read `workflows/memory-prune.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| prune_memory | `tests/test_prune_memory.py` | Entropy audit, tombstone creation, retention period, merge preserves source_ids |
| prune_nondestructive | `tests/test_prune_memory.py` | Original file preserved after prune, no hard deletes |

## Examples

- **Stale entry**: `memory-prune --action tombstone --id ADR-002 --reason "stale 120 days"` → creates tombstone, sets status: archived
- **Merge duplicates**: `memory-prune --action merge --source1 ADR-003 --source2 ADR-007` → creates merged ADR-018, originals get `replaced_by: ADR-018`

