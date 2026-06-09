---
name: lesson-capture
description: >
  Capture a durable lesson learned from an error, repeated failure, or recovered mistake.
  Use when: a failure pattern should not be repeated by future agents.
  Not for: recording planned design choices or generic note-taking.
  Output: a durable lesson record with source anchors and prevention guidance.
triggers:
  - "lesson learned"
  - "don't repeat this"
  - "capture that mistake"
  - "LL-"
  - "capture lesson"
  - "lesson"
---

# Lesson Capture

Route durable failure-learning requests to the lesson-capture workflow.

## What this skill does

1. Confirms the task is about a mistake, failure, or repeated pitfall
2. Routes lesson creation to the lesson-capture workflow
3. Keeps lessons distinct from design decisions and general notes

## When to use

- A failure should become reusable project memory
- A repeated pitfall needs a documented guard

## When NOT to use

- The task is a planned architecture choice
- The task is only metadata validation
- The task is a generic scratch note

## Execution

→ Read `workflows/lesson-capture.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| write_lesson | `tests/test_write_lesson.py` | LL ID allocation, quality gates, write-durable |
| lesson_dedup | `tests/test_write_lesson.py` | Duplicate lesson detection, candidate storage |
| lesson_quality_gates | `tests/test_write_lesson.py` | QG1-QG5 enforcement, missing slot rejection |

## Examples

- **New lesson**: `lesson-capture --pitfall "Port 8080 conflict" --root-cause "Both services hardcoded default port" --trigger "When two services start with default configs" --fix "Assigned distinct ports via env vars" --guard "scripts/port-check.py pre-flight" --source-anchors "ADR-008,incident-2026-05-20"` → writes LL-XXX to `docs/lessons/`
- **Duplicate detection**: `lesson-capture --pitfall "Port 8080 conflict" ...` → if LL-023 exists with same pitfall+root_cause, writes as candidate with `possible_duplicate_of: LL-023`
