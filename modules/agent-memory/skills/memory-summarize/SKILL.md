---
name: memory-summarize
description: >
  Generate durable conversation summaries from stable source material.
  Use when: working context should be compacted into a durable summary segment.
  Not for: summarizing a single message or summarizing an existing summary.
  Output: a durable summary segment with provenance.
triggers:
  - "summarize conversation"
  - "generate thread summary"
  - "summarize thread"
  - "conversation summary"
---

# Memory Summarize

Route stable-summary generation requests to the memory-summarize workflow.

## What this skill does

1. Confirms the task is about durable summarization rather than raw chat rendering
2. Routes summary generation to the memory-summarize workflow
3. Enforces the separation between source material and summary artifacts

## When to use

- A conversation has enough stable context to compact
- Durable summary memory is needed for future agents

## When NOT to use

- The task is a single-message summary
- The input is already a summary artifact (rules.md §7 — no-summary-of-summary)

## Execution

→ Read `workflows/memory-summarize.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| summarize_conversation | `tests/test_summarize_conversation.py` | Summary-of-summary rejection, L1 generation, L2 rejection |
| summarize_eligibility | `tests/test_summarize_conversation.py` | Eligibility thresholds (quiet window, min messages) |

## Examples

- **Eligible conversation**: `memory-summarize --source conversation-42.txt` → writes SUM-YYYYMMDD-HHMM-slug to `docs/summaries/`
- **Rejected summary-of-summary**: `memory-summarize --source docs/summaries/SUM-2026-05-25.md` → REJECTED per rules.md §7
