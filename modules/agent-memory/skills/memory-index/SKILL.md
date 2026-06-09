---
name: memory-index
description: >
  Build or rebuild the searchable memory index from durable project documents.
  Use when: durable memory has changed and retrieval must be refreshed.
  Not for: cold-starting a new repo or directly answering a recall question.
  Output: an index rebuild report for durable memory artifacts.
triggers:
  - "rebuild index"
  - "index docs"
  - "reindex"
  - "build index"
---

# Memory Index

Route index build and rebuild requests to the memory-index workflow.

## What this skill does

1. Confirms the task is about rebuilding the searchable memory artifact
2. Routes index refresh requests to the memory-index workflow
3. Keeps indexing separate from retrieval and bootstrap flows

## When to use

- Durable memory documents changed and search must be refreshed
- An explicit rebuild is requested

## When NOT to use

- The task is to search memory
- The task is to bootstrap memory for a new project

## Execution

→ Read `workflows/memory-index.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| rebuild_index | `tests/test_rebuild_index.py` | Full rebuild, content hash consistency |
| incremental_rebuild | `tests/test_rebuild_index.py` | Different files produce different hashes |

## Examples

- **Full rebuild**: `memory-index --scope full` → re-indexes all durable docs from scratch
- **Incremental rebuild**: `memory-index --scope incremental` → only re-indexes docs changed since last build
