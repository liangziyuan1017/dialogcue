---
name: decision-record
description: >
  Record or update a durable architecture or design decision in Why-First format.
  Use when: a project decision should become durable memory for future agents.
  Not for: lessons learned from failures or metadata-only validation.
  Output: a durable decision record with frontmatter and decision rationale.
triggers:
  - "record this decision"
  - "create ADR"
  - "architecture decision"
  - "record decision"
  - "document this choice"
---

# Decision Record

Route durable decision capture requests to the decision-record workflow.

## What this skill does

1. Confirms the task is about preserving a project decision
2. Routes decision capture to the decision-record workflow
3. Ensures decisions are separated from lessons and metadata checks

## When to use

- A design or architecture choice should be preserved
- Future agents will need the reasoning behind a choice

## When NOT to use

- The task is a lesson from a mistake
- The task is only checking document metadata
- The task is only searching past knowledge

## Execution

→ Read `workflows/decision-record.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| write_decision | `tests/test_write_decision.py` | ADR ID allocation, valid frontmatter, write-durable, optimistic concurrency |
| decision_dedup | `tests/test_write_decision.py` | Duplicate title detection, candidate storage |

## Examples

- **New decision**: `decision-record --title "Use PostgreSQL 16" --what "Adopt PG16 as primary DB" --why "Better JSON support" --tradeoff "MySQL 8: simpler ops but weaker JSON"` → writes ADR-XXX to `docs/decisions/`
- **Update decision**: `decision-record --id ADR-008 --status accepted` → updates existing ADR with optimistic concurrency
