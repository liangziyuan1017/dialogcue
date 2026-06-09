---
name: memory-search
description: >
  Search durable project memory for prior decisions, lessons, summaries, and validated knowledge.
  Use when: an agent needs historical project context before acting.
  Not for: creating new durable knowledge or validating metadata compliance.
  Output: ranked memory results with source anchors.
triggers:
  - "search memory"
  - "find decision"
  - "what did we decide about"
  - "recall"
  - "has this happened before"
  - "memory search"
  - "search for"
---

# Memory Search

Route requests for durable project recall to the memory-search workflow.

## What this skill does

1. Confirms the task is retrieval-oriented rather than write-oriented
2. Routes recall requests to the memory search workflow
3. Keeps retrieval selection logic out of the runtime layer

## When to use

- The task asks what the project already decided, learned, or documented
- An agent needs prior context before making a change

## When NOT to use

- A new decision must be recorded
- A new lesson must be captured
- Metadata compliance needs validation

## Execution

→ Read `workflows/memory-search.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| search_memory | `tests/test_search_memory.py` | Exact ID lookup (top-1), concept search, doc_kind filtering |
| search_degradation | `tests/test_search_memory.py` | Semantic degradation to lexical-only |

## Examples

- **Hybrid search**: `memory-search --query "port allocation strategy" --limit 5` → returns ranked results including ADR-008
- **Exact ID lookup**: `memory-search --query "ADR-008" --limit 1` → ADR-008 at rank 1
- **Filtered search**: `memory-search --query "database" --doc-kind decision --limit 3` → only decision documents
