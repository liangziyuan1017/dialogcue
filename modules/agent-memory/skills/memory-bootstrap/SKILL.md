---
name: memory-bootstrap
description: >
  Bootstrap durable memory for a new or external project from existing stable artifacts.
  Use when: a project has no established memory layer and agents need cold-start context.
  Not for: incremental index refreshes or routine search.
  Output: a bootstrap summary plus initial durable memory setup state.
triggers:
  - "bootstrap memory"
  - "cold start project"
  - "expedition memory"
  - "bootstrap project"
  - "initialize memory"
  - "cold start"
---

# Memory Bootstrap

Route cold-start memory setup requests to the memory-bootstrap workflow.

## What this skill does

1. Confirms the task is a first-run or external-project memory setup
2. Routes bootstrap work to the memory-bootstrap workflow
3. Keeps bootstrap concerns separate from normal indexing and retrieval

## When to use

- A project has no memory index yet
- Agents need durable starting context for a repo they have not worked in before

## When NOT to use

- The task is a routine index rebuild
- The task is to search already-available memory

## Execution

→ Read `workflows/memory-bootstrap.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| bootstrap_memory | `tests/test_bootstrap_memory.py` | Discover docs (structured=10, generic=0), validate-each, bootstrap report |
| bootstrap_idempotent | `tests/test_bootstrap_memory.py` | Running twice produces same result |

## Examples

- **Structured repo**: `memory-bootstrap --root fixtures/structured-repo/` → discovers 10 docs, validates, builds index
- **Empty repo**: `memory-bootstrap --root fixtures/generic-repo/` → 0 docs found, empty index is valid
