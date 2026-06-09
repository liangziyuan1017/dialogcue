# Governance Review Workflow

> **Skill**: `skills/governance-review/SKILL.md`
> **Purpose**: Review work against module principles, boundaries, and governance rules.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `rule-check` | `scripts/rule-check.py` | Check a proposed change against `rules.md` invariants |
| `principle-check` | `scripts/principle-check.py` | Check a proposed change against `refs/first-principles.md` |
| `boundary-check` | `scripts/boundary-check.py` | Check a proposed change against memory boundaries (`rules.md §2`) |
| `review-report` | `scripts/review-report.py` | Produce a governance review report with pass/violation/caution |

## Execution Order

1. **Parse proposed change**: Accept a description of the proposed work.
   - Input can be: a file path, a diff, a natural-language description, or a feature spec.
   - Supported formats: `--file <PATH>`, `--diff <DIFF_TEXT>`, `--description "<TEXT>"`.

2. **Check invariants** (`rules.md §1`):
   ```
   scripts/rule-check.py --rules invariants --against <INPUT>
   ```
   → Checks:
   - Is the change host-agnostic? (No host-specific logic in core files.)
   - Does it follow deterministic navigation? (registry → router → skill → workflow → scripts.)
   - Is working_file.md the only writable file during runtime?
   - Are documents the source of truth, not the index?
   → Output: `PASS | VIOLATION: <rule_description>`.

3. **Check memory boundaries** (`rules.md §2`):
   ```
   scripts/boundary-check.py --against <INPUT>
   ```
   → Checks:
   - Does the change write raw chats, speculative ideas, or tool logs to durable memory?
   - Does conversation content get promoted through the gate (decision/lesson/summary/validated-note)?
   → Output: `PASS | VIOLATION: <boundary_description>`.

4. **Check authority model** (`rules.md §3`):
   ```
   scripts/rule-check.py --rules authority --against <INPUT>
   ```
   → Checks:
   - If creating `constitutional` or `always_on` knowledge, is there a human-reviewed flow?
   - Are new entries defaulting to `observed + query + active`?
   → Output: `PASS | VIOLATION: <authority_rule>`.

5. **Check concurrency** (`rules.md §4`):
   ```
   scripts/rule-check.py --rules concurrency --against <INPUT>
   ```
   → Checks:
   - Are writes append-first?
   - Are deletes tombstones, not hard deletes?
   - Is ID allocation atomic?
   → Output: `PASS | VIOLATION: <concurrency_rule>`.

6. **Check privacy** (`rules.md §5`):
   ```
   scripts/rule-check.py --rules privacy --against <INPUT>
   ```
   → Checks:
   - Does the change expose secrets, credentials, customer names, proprietary URLs?
   - Does `exportability` match the content?
   → Output: `PASS | VIOLATION: <privacy_rule>`.

7. **Check compression** (`rules.md §6`):
   ```
   scripts/rule-check.py --rules compression --against <INPUT>
   ```
   → Checks:
   - Is compression non-destructive?
   - Are tombstones created before removal?
   - Is 90-day retention respected?
   → Output: `PASS | VIOLATION: <compression_rule>`.

8. **Check no-summary-of-summary** (`rules.md §7`):
   ```
   scripts/rule-check.py --rules summary --against <INPUT>
   ```
   → If input is already a summary → `VIOLATION: rules.md §7 — no-summary-of-summary`.
   → Output: `PASS | VIOLATION`.

9. **Check principles** (`refs/first-principles.md`):
   ```
   scripts/principle-check.py --against <INPUT>
   ```
   → Checks alignment with first principles (source of truth, rebuildable index, fail-closed, etc.).

10. **Generate review report**:
    ```
    scripts/review-report.py --results <RESULTS_JSON>
    ```
    → Output:
    ```
    === Governance Review Report ===
    Result: PASS | CAUTION | VIOLATION
    
    Violations:
    - rules.md §4: Proposed deletion without tombstone — VIOLATION
    
    Cautions:
    - rules.md §2: Change writes to docs/ without promotion gate — verify content qualifies
    
    Passed: 7 of 8 rule categories
    ```
    → Exit code: 0 = all pass, 1 = violations found.

## Success Conditions

- All applicable rule categories return PASS or CAUTION.
- No VIOLATION in any category.

## Failure Conditions

- Any VIOLATION → exit code 1, report which rule was violated.
- Input cannot be parsed → exit code 1, report `"unrecognized input format"`.

## Severity Levels

| Level | Meaning | Exit Code |
|---|---|---|
| PASS | Change aligns with all rules | 0 |
| CAUTION | Change is directionally correct but needs attention | 0 (with warnings) |
| VIOLATION | Change breaks an invariant or rule | 1 |

## Next Step

Governance review is a terminal capability — it produces a report and does not chain to another skill. Based on the result:

| Result | Action |
|---|---|
| PASS | Proceed with the proposed change |
| CAUTION | Review the caution items, then proceed if acceptable |
| VIOLATION | Fix the violation before proceeding. Re-run governance-review after the fix. |

## Document Sync Rule

Governance review is read-only. No documents are created or modified. The review report is written to stdout only.

## Iron Laws

- A VIOLATION in any rule category blocks the proposed change. There are no "acceptable violations."
- Delete without tombstone is always a VIOLATION (rules.md §4).
- Summary-of-summary is always a VIOLATION (rules.md §7).
- Exposing secrets or credentials is always a VIOLATION (rules.md §5).

## Anti-patterns

- **Proceeding after VIOLATION**: A governance review that reports VIOLATION means the change must not proceed. Fix the violation and re-run.
- **Ignoring CAUTION items**: Cautions are not blockers, but they should be reviewed and acknowledged before proceeding.
- **Governance as post-hoc check**: Governance review should be run before the change is applied, not after. Prevention, not detection.

## Test References

| Test | Path |
|---|---|
| governance_review | `tests/test_governance_review.py` |

## Reproducible Example

```bash
# Proposed change: delete ADR-003 without tombstone
scripts/rule-check.py --rules concurrency --against "DELETE docs/decisions/ADR-003.md"
# Expected: "VIOLATION: rules.md §4 — tombstone required before deletion"

# Proposed change: re-summarize a summary
scripts/rule-check.py --rules summary --against "Summarize docs/summaries/SUM-2026-05-25.md"
# Expected: "VIOLATION: rules.md §7 — no-summary-of-summary"

# Proposed change: aligned new decision
scripts/rule-check.py --rules invariants --against "Create ADR-015 in docs/decisions/"
scripts/rule-check.py --rules authority --against "Create ADR-015 with authority: observed, status: draft"
scripts/boundary-check.py --against "Create ADR-015 — decision record, not raw chat"
scripts/principle-check.py --against "Create ADR-015 — append-first write to docs/"
scripts/review-report.py --results '[{"category":"invariants","result":"PASS"},{"category":"authority","result":"PASS"},{"category":"boundary","result":"PASS"},{"category":"principles","result":"PASS"}]'
# Expected: "Result: PASS, 4 of 4 categories passed"
```
