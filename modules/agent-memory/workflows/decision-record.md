# Decision Record Workflow

> **Skill**: `skills/decision-record/SKILL.md`
> **Purpose**: Record or update a durable architecture or design decision in Why-First format.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `id-allocate` | `scripts/id-allocate.py` | Atomically allocate the next ADR ID (ADR-001, ADR-002, ...) |
| `frontmatter-lint` | `scripts/frontmatter-lint.py` | Validate frontmatter against `schemas/frontmatter.schema.yaml` |
| `write-durable` | `scripts/write-durable.py` | Write (append-first) a decision document to the host project's `docs/decisions/` |
| `index-rebuild` | `scripts/index-rebuild.py` | Trigger incremental reindex after successful write |
| `lexical-search` | `scripts/lexical-search.py` | Search for duplicate decisions by title |
| `content-hash` | `scripts/content-hash.py` | Compute content hash for optimistic concurrency |

## Execution Order

1. **Parse input**: Accept a decision payload with required fields:
   ```yaml
   title: <string>           # One-line decision summary
   what: <string>            # What was decided
   why: <string>             # Why this choice
   tradeoff: <string>        # Alternatives considered and rejected
   feature_ids: [<strings>]  # Optional related feature IDs
   topics: [<strings>]       # Optional topic tags
   ```

2. **Allocate ID**:
   ```
   scripts/id-allocate.py --kind ADR
   ```
   → Output: `ADR-XXX` (next sequential ID).
   → Rule: `rules.md §4` — reserves ID via `.agent-memory/locks/id-allocation.lock`; rejects duplicates; retries on collision.

3. **Assemble frontmatter**:
   ```yaml
   id: <ALLOCATED_ID>
   title: <TITLE>
   doc_kind: decision
   feature_ids: [<IDS>]
   topics: [<TOPICS>]
   status: draft
   created: <TODAY>
   updated: <TODAY>
   schema_version: 1
   ```

4. **Validate frontmatter**:
   ```
   scripts/frontmatter-lint.py --input <FRONTMATTER_YAML>
   ```
   → Output: `valid` or list of violations.
   → Required fields must all be present per `schemas/frontmatter.schema.yaml`.
   → If `feature_ids` or `topics` are empty, use `[]` (valid).

5. **Halt on validation failure**: If `frontmatter-lint` reports violations, stop and return violations. Do not write.

6. **Check for duplicates**:
   ```
   scripts/lexical-search.py --query "<TITLE>" --doc-kind decision --limit 3
   ```
   → If an existing ADR has the same title → flag as `possible_duplicate_of: <EXISTING_ID>`.
   → Write with `status: candidate` instead of `draft`.
   → Rule: `rules.md §4` — duplicate ADRs stored as candidates, not silently overwritten.

7. **Write decision document** (append-first):
   ```
   scripts/write-durable.py --path docs/decisions/<SLUG>.md --content <ASSEMBLED_DOC>
   ```
   → Output: confirmation of write with file path.
   → Rule: `rules.md §4` — all writes are append-first; updates use optimistic concurrency.
   → Content includes: frontmatter + Why-First sections (What, Why, Tradeoff table).

8. **Trigger incremental reindex**:
   ```
   scripts/index-rebuild.py --scope incremental --files docs/decisions/<SLUG>.md
   ```
   → Rule: `rules.md §1` — explicit reindex after each successful durable write.

## Update Existing Decision

If input includes an existing `id` (e.g., `ADR-008`) with changed `status`, `updated`, or `replaced_by`:

1. **Read existing document**:
   ```
   scripts/content-hash.py --file docs/decisions/<SLUG>.md
   ```
   → Capture current content hash for optimistic concurrency.

2. **Apply optimistic concurrency check**:
   ```
   scripts/write-durable.py --path docs/decisions/<SLUG>.md --update-frontmatter '<UPDATES>' --if-unmodified-since <READ_TIMESTAMP>
   ```
   → If changed since read → reject, require re-read (exit code 2).
   → If unchanged → append update, bump `updated` to today.

3. **Validate updated frontmatter**:
   ```
   scripts/frontmatter-lint.py --file docs/decisions/<SLUG>.md
   ```

4. **Trigger incremental reindex**:
   ```
   scripts/index-rebuild.py --scope incremental --files docs/decisions/<SLUG>.md
   ```
   → Rule: `rules.md §4` — status changes are not tombstones; tombstones are for removal only.

## Success Conditions

- `id-allocate` returns a unique, unused ADR ID.
- `frontmatter-lint` returns `valid`.
- `write-durable` confirms file written to `docs/decisions/`.
- `index-rebuild` confirms the new doc is indexed.

## Failure Conditions

- `id-allocate` fails (lock timeout, disk error) → exit code 1.
- `frontmatter-lint` reports required-field violations → exit code 1, report violations.
- `write-durable` fails (disk error, path not writable) → exit code 1.
- Duplicate title detected → write as candidate, exit code 0 with warning.

## Next Step

After a decision is successfully written or updated:

→ `memory-index` — incremental reindex is triggered automatically (step 8). If reindex fails, the decision is still written; run `memory-index --scope incremental` manually.

If the decision references a feature doc that should be updated:
→ Update `docs/features/Fxxx-*.md` with the decision ID and rationale summary.

## Document Sync Rule

After writing a decision record:
1. The new document is written to `docs/decisions/<SLUG>.md`.
2. Incremental reindex updates `.agent-memory/index.json`.
3. If `feature_ids` are specified, the corresponding feature docs should reference the new ADR ID in their decision log section.

## Iron Laws

- Every decision must have a `why` — decisions without rationale are invalid.
- Duplicate decisions are stored as candidates, never silently overwritten.
- ID allocation is atomic — no two decisions may share the same ADR ID.
- Writes are append-first — existing content is never overwritten without optimistic concurrency.

## Anti-patterns

- **Decision without rationale**: A decision that states "what" but not "why" violates the Why-First format. Reject.
- **Silent overwrite on duplicate**: If a duplicate title is detected, the new decision must be stored as `status: candidate`, not overwrite the existing one.
- **Hard delete of decisions**: Decisions are never hard-deleted. Use `memory-prune` with tombstone.

## Test References

| Test | Path |
|---|---|
| write_decision | `tests/test_write_decision.py` |
| decision_dedup | `tests/test_write_decision.py` |

## Reproducible Example

```bash
# New decision
scripts/id-allocate.py --kind ADR
# Expected: "ADR-015" (or next available)

scripts/frontmatter-lint.py --input '
id: ADR-015
title: "Use PostgreSQL 16 as primary database"
doc_kind: decision
feature_ids: [F042]
topics: [database, persistence]
status: draft
created: 2026-05-25
updated: 2026-05-25
schema_version: 1
'
# Expected: "valid"

scripts/write-durable.py --path docs/decisions/015-postgresql-choice.md --content '...'
# Expected: "written: docs/decisions/015-postgresql-choice.md"

scripts/index-rebuild.py --scope incremental --files docs/decisions/015-postgresql-choice.md
# Expected: "1 doc re-indexed"

# Update existing decision
scripts/write-durable.py --path docs/decisions/ADR-008.md --content '...' --if-unmodified-since 2026-05-24T12:00:00Z
# If unchanged since: "updated: docs/decisions/ADR-008.md"
# If changed since: "REJECTED: document modified since read; re-read and retry"
```
