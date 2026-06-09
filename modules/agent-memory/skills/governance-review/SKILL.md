---
name: governance-review
description: >
  Review work against module principles, boundaries, and governance rules.
  Use when: proposed work should be checked against durable memory policy and first principles.
  Not for: creating new rules or capturing new project knowledge.
  Output: a governance review report with violations, cautions, or passes.
triggers:
  - "check against principles"
  - "governance check"
  - "is this aligned"
  - "principle check"
  - "governance review"
---

# Governance Review

Route governance and principle checks to the governance-review workflow.

## What this skill does

1. Confirms the task is evaluative rather than generative
2. Routes principle checks to the governance-review workflow
3. Keeps governance review separate from decision capture and metadata validation

## When to use

- Work must be checked against module constraints
- A change needs policy or principle review

## When NOT to use

- A new decision must be recorded
- A new lesson must be captured
- The task is only a metadata check

## Execution

→ Read `workflows/governance-review.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| governance_review | `tests/test_governance_review.py` | Delete without tombstone violation, summary-of-summary violation, principle check, boundary check |

## Examples

- **Check proposed change**: `governance-review --description "Delete ADR-003 without tombstone"` → VIOLATION: rules.md §4
- **Aligned change**: `governance-review --description "Create ADR-015 with authority: observed"` → PASS
