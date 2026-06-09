# Lesson Capture Workflow

> **Skill**: `skills/lesson-capture/SKILL.md`
> **Purpose**: Capture a durable lesson learned from an error, repeated failure, or recovered mistake.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `id-allocate` | `scripts/id-allocate.py` | Atomically allocate the next lesson ID (LL-001, LL-002, ...) |
| `frontmatter-lint` | `scripts/frontmatter-lint.py` | Validate frontmatter against `schemas/frontmatter.schema.yaml` and `schemas/lesson.schema.yaml` |
| `lexical-search` | `scripts/lexical-search.py` | Search for duplicate lessons by pitfall + root_cause |
| `write-durable` | `scripts/write-durable.py` | Write (append-first) a lesson document to `docs/lessons/` |
| `index-rebuild` | `scripts/index-rebuild.py` | Trigger incremental reindex after successful write |

## Execution Order

1. **Parse input**: Accept a lesson payload with required slots:
   ```yaml
   pitfall: <string>           # What went wrong? One sentence.
   root_cause: <string>        # Why did it happen? Underlying cause.
   trigger_conditions: <string> # When will this recur?
   fix: <string>               # How was it resolved?
   guard: <string>             # How do we prevent it next time?
   source_anchors: [<strings>] # At least 1 reference to where this was observed
   ```

2. **Allocate ID**:
   ```
   scripts/id-allocate.py --kind LL
   ```
   → Output: `LL-XXX` (next sequential ID).
   → Rule: `rules.md §4` — atomic allocation via lock file.

3. **Assemble frontmatter**:
   ```yaml
   id: <ALLOCATED_ID>
   title: <PITFALL_SUMMARY>
   doc_kind: lesson
   feature_ids: []
   topics: [<INFERRED_TOPICS>]
   status: draft
   created: <TODAY>
    schema_version: 1
    ```
   → Frontmatter assembly uses field values from steps 1-2; no separate script needed (fields are deterministic from input).

4. **Validate frontmatter**:
   ```
   scripts/frontmatter-lint.py --input <FRONTMATTER_YAML> --schema lesson
   ```
   → Output: `valid` or list of violations.
   → Required fields: `id`, `title`, `doc_kind`, `created`, `schema_version`.
   → `doc_kind` must be `lesson`.

5. **Halt on validation failure**: If violations found, stop and report. Do not write.

6. **Run quality gates**:
   ```
   scripts/frontmatter-lint.py --input <FRONTMATTER_YAML> --schema lesson --check-quality-gates
   ```
   → Quality gates defined in `schemas/lesson.schema.yaml`:
     - QG1: Pitfall is a single, specific sentence
     - QG2: Root cause is a cause, not a symptom
     - QG3: Trigger conditions are concrete and reproducible
     - QG4: Guard is executable (script, check, or automated rule)
     - QG5: At least 1 source anchor present
   → If any gate fails → reject with `quality_gate_failures: [QG1, ...]`, exit code 1.
   → Rule: `rules.md §2` — quality gates are schema-enforced, not workflow-enforced.

7. **Check for duplicate lessons**:
   ```
   scripts/lexical-search.py --query "<PITFALL> <ROOT_CAUSE>" --doc-kind lesson --limit 5
   ```
   → If an existing lesson has matching pitfall AND root_cause:
   - Write new lesson as candidate.
   - Set `possible_duplicate_of: <EXISTING_LL_ID>`.
   - Set `authority: candidate` (not `observed`).
   - Exit code 0 with warning.
   → Rule: `rules.md §4` — duplicate lessons stored as candidates.

8. **Write lesson document** (append-first):
   ```
   scripts/write-durable.py --path docs/lessons/<SLUG>.md --content <ASSEMBLED_DOC>
   ```
   → Content: frontmatter + 7 sections: Pitfall, Root Cause, Trigger Conditions, Fix, Guard, Source Anchors, Prevention Notes.
   → Default `authority: observed` for new lessons (unless duplicate → `candidate`).

9. **Trigger incremental reindex**:
   ```
   scripts/index-rebuild.py --scope incremental --files docs/lessons/<SLUG>.md
   ```

## Success Conditions

- `id-allocate` returns a unique, unused LL ID.
- All 5 quality gates pass.
- `frontmatter-lint` returns `valid`.
- `write-durable` confirms file written.
- `index-rebuild` confirms indexing.

## Failure Conditions

- Quality gate failure → exit code 1, report which gates failed.
- `frontmatter-lint` reports violations → exit code 1.
- Duplicate detected → exit code 0 with warning, stored as candidate.
- Less than 1 source anchor → QG5 failure.

## Next Step

After a lesson is successfully written:

→ `memory-index` — incremental reindex is triggered automatically (step 9). If reindex fails, the lesson is still written; run `memory-index --scope incremental` manually.

If the lesson's guard references a script or check that should be created:
→ Create the guard artifact in the appropriate `scripts/` or `tests/` location.

## Document Sync Rule

After writing a lesson record:
1. The new document is written to `docs/lessons/<SLUG>.md`.
2. Incremental reindex updates `.agent-memory/index.json`.
3. If `feature_ids` are specified, the corresponding feature docs should reference the new LL ID.

## Iron Laws

- All 5 quality gates (QG1–QG5) must pass before a lesson enters durable memory.
- At least 1 source anchor is required — lessons without evidence are invalid.
- Duplicate lessons are stored as candidates, never silently overwritten.
- The guard must be executable (script, check, or automated rule) — aspirational guards are rejected.

## Anti-patterns

- **Lesson without evidence**: A lesson that describes a pitfall but provides no source anchor (where the error was observed) fails QG5. Reject.
- **Aspirational guard**: A guard like "be more careful" is not executable. The guard must be a script, check, or automated rule. Reject.
- **Root cause as symptom**: "The port was wrong" is a symptom, not a root cause. "Both services hardcoded the default port without configuration" is a root cause. Reject symptoms at QG2.
- **Hard delete of lessons**: Lessons are never hard-deleted. Use `memory-prune` with tombstone.

## Test References

| Test | Path |
|---|---|
| write_lesson | `tests/test_write_lesson.py` |
| lesson_dedup | `tests/test_write_lesson.py` |
| lesson_quality_gates | `tests/test_write_lesson.py` |

## Reproducible Example

```bash
# New lesson
scripts/id-allocate.py --kind LL
# Expected: "LL-042"

scripts/frontmatter-lint.py --input '
id: LL-042
title: "Port 8080 conflict between API and dashboard services"
doc_kind: lesson
status: draft
created: 2026-05-25
schema_version: 1
' --schema lesson
# Expected: "valid"

# Quality gates pass (QG1-QG5 all met):
# QG1: "Port 8080 conflict" — specific ✓
# QG2: "Both services hardcoded default port" — root cause ✓
# QG3: "When two services are started with default configs" — concrete ✓
# QG4: "scripts/port-check.py — pre-flight port conflict detection" — executable ✓
# QG5: 2 source anchors provided ✓

scripts/write-durable.py --path docs/lessons/042-port-8080-conflict.md --content '...'
# Expected: "written: docs/lessons/042-port-8080-conflict.md"

scripts/index-rebuild.py --scope incremental --files docs/lessons/042-port-8080-conflict.md
# Expected: "1 doc re-indexed"

# Duplicate detection
scripts/lexical-search.py --query "Port 8080 conflict Both services hardcoded" --doc-kind lesson --limit 5
# Expected: returns LL-023 with high similarity
# → writes as candidate with possible_duplicate_of: LL-023
```
