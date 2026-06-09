# Lessons Template — LL-XXX

> Normalized from clowder-ai public-lessons.md.
> 7-slot template with 5 quality gates for capturing lessons learned.

## The 7 Slots

| Slot | Name | Description | Required |
|------|------|-------------|----------|
| 1 | Pitfall | What went wrong? One sentence. | Yes |
| 2 | Root Cause | Why did it happen? Trace to the underlying cause, not the symptom. | Yes |
| 3 | Trigger Conditions | Under what conditions will this recur? Be specific. | Yes |
| 4 | Fix | How was it resolved in this instance? | Yes |
| 5 | Guard (Executable) | What mechanism prevents recurrence? Must be a script, test, CI rule, or automated check. NOT "be careful." | Yes |
| 6 | Source Anchor | Where is the evidence? At least 1 file path or commit SHA. Recommended: 2. | Yes |
| 7 | Related | Related ADR IDs, lesson IDs, or feature IDs. | No |

## First-Principles Root Cause (Optional — Slot 8)

Which axiom (P1-P5) does this lesson trace to? Only fill if a real failure case supports it. No speculative principle assignments.

## The 5 Quality Gates

A lesson must pass ALL FIVE gates before acceptance:

| Gate | Name | Check |
|------|------|-------|
| QG1 | Source anchor exists | At least 1 entry in slot 6 |
| QG2 | Timeliness verified | No subsequent addendum or discussion has invalidated this lesson |
| QG3 | Executable guard present | Slot 5 references a real script, test, CI rule, or automated check — not just prose |
| QG4 | Principle slot constrained | Slot 8 is empty unless supported by a real failure case |
| QG5 | Dedup passed | No existing LL-XXX describes the same pitfall with the same root cause |

## ID Rules

- Format: `LL-XXX` (three digits, incrementing)
- IDs are never reused or renumbered
- Status: `draft` → `validated` → `archived`
- Major rewrites keep the same ID; record `updated` date and reason

## Timeliness Check

Before promoting a lesson, verify it hasn't been invalidated by:
- ADR updates or addenda within 30 days
- Bug report follow-ups within 7 days
- Discussion conclusions within 14 days
