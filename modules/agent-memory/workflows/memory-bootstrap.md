# Memory Bootstrap Workflow

> **Skill**: `skills/memory-bootstrap/SKILL.md`
> **Purpose**: Bootstrap durable memory for a new or external project from existing stable artifacts.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `discover-docs` | `scripts/discover-docs.py` | Scan a repo root for durable memory documents (ADRs, lessons, summaries) |
| `validate-each` | `scripts/validate-each.py` | Run `schemas/frontmatter.schema.yaml` validation against each discovered doc |
| `index-rebuild` | `scripts/index-rebuild.py` | Build initial searchable memory index from validated docs |
| `bootstrap-report` | `scripts/bootstrap-report.py` | Produce a human-readable bootstrap summary |

## Execution Order

1. **Confirm target**: Accept a repo root path as input. If not provided, default to `$PWD`.
   ```
   scripts/discover-docs.py --root <REPO_ROOT>
   ```
   → Output: list of discovered doc paths under `docs/decisions/`, `docs/lessons/`, `docs/summaries/`.

2. **Validate all discovered docs**:
   ```
   scripts/validate-each.py --files <DISCOVERED_FILES>
   ```
   → Output: per-file validation report (pass / violations list).
   → Rule: `rules.md §8` — schema_version and module_version must match.

3. **Halt on structural failures**: If any doc fails required-field validation (`id`, `title`, `doc_kind`, `created`, `schema_version`), stop and report violations. Do not proceed to indexing.

4. **Build initial index**:
   ```
   scripts/index-rebuild.py --scope full --root <REPO_ROOT>
   ```
   → Output: index rebuild report (docs indexed, hash conflicts, index location).
   → Rule: `rules.md §1` — index is a rebuildable artifact. Source of truth is documents.

5. **Generate bootstrap report**:
   ```
   scripts/bootstrap-report.py --discovered <COUNT> --validated <COUNT> --indexed <COUNT>
   ```
   → Output: human-readable summary written to stdout and optionally to `working_file.md`.

6. **Handle no-docs case**: If `discover-docs` returns zero results:
   ```
   scripts/index-rebuild.py --scope full --root <REPO_ROOT>
   ```
   → Writes minimal index with metadata only.
   → Report: `"No structured durable docs found at <ROOT>. Index is empty but valid."`
   → Exit code 0 (not a failure — just a cold start).

## Success Conditions

- `discover-docs` returns a file list (empty is OK for cold start).
- `validate-each` returns zero required-field violations.
- `index-rebuild` produces a consistent index artifact in `.agent-memory/`.
- `bootstrap-report` produces a readable summary.

## Failure Conditions

- Any document fails `validate-each` on required fields → **halt**, report violations, exit code 1.
- `index-rebuild` fails (lock contention, disk error) → **halt**, report error, exit code 1.
- Repo root is not a directory → **halt**, exit code 1.

## Idempotency

Running bootstrap twice on the same repo must:
- Not create duplicate index entries.
- Not modify already-validated documents.
- Produce the same bootstrap report (same doc count, same index hash).

## Next Step

After a successful bootstrap:

→ `memory-search` — the index is now available for retrieval.
→ `metadata-enforce` — run a compliance check to verify all discovered documents meet frontmatter requirements.

If no structured documents were found:
→ The project may need manual decision and lesson creation. Route to `decision-record` or `lesson-capture` as needed.

## Document Sync Rule

After bootstrap:
1. The index artifact is written to `.agent-memory/index.json`.
2. Content hashes are computed for all discovered documents.
3. No durable documents (docs/decisions/, docs/lessons/, docs/summaries/) are modified — bootstrap is read-only plus index creation.
4. The bootstrap report may be written to `working_file.md` progress notes.

## Iron Laws

- Bootstrap is idempotent — running it twice on the same repo must not create duplicate index entries or modify existing documents.
- Documents that fail required-field validation halt the bootstrap. Do not proceed to indexing with invalid documents.
- The index is a rebuildable artifact — if bootstrap fails mid-way, re-running it produces the same result.

## Anti-patterns

- **Bootstrap on a repo with an existing index**: If `.agent-memory/index.json` already exists, bootstrap should rebuild the index rather than fail. Use `memory-index --scope full` for routine refreshes.
- **Skipping validation**: Never skip the validate-each step. Invalid documents in the index corrupt search results.
- **Modifying source documents during bootstrap**: Bootstrap must not alter the discovered documents. It reads and indexes only.

## Test References

| Test | Path |
|---|---|
| bootstrap_memory | `tests/test_bootstrap_memory.py` |
| bootstrap_idempotent | `tests/test_bootstrap_memory.py` |

## Reproducible Example

```bash
# Bootstrap memory for a structured repo fixture
scripts/discover-docs.py --root fixtures/structured-repo/
# Expected: returns 5–10 file paths under docs/decisions/ and docs/lessons/

scripts/validate-each.py --files fixtures/structured-repo/docs/decisions/*.md fixtures/structured-repo/docs/lessons/*.md
# Expected: all pass, 0 violations

scripts/index-rebuild.py --scope full --root fixtures/structured-repo/
# Expected: "12 docs indexed, 0 hash conflicts, index written to .agent-memory/"

scripts/bootstrap-report.py --discovered 12 --validated 12 --indexed 12
# Expected: "Bootstrap complete. 12 durable docs discovered, all validated, index ready."
```

```bash
# Bootstrap memory for a repo with no structured docs
scripts/discover-docs.py --root fixtures/generic-repo/
# Expected: returns 0 files

# No validate-each needed

scripts/index-rebuild.py --scope full --root fixtures/generic-repo/
# Expected: "0 docs indexed, index is empty but valid"

scripts/bootstrap-report.py --discovered 0 --validated 0 --indexed 0
# Expected: "No structured durable docs found. Index is empty but valid."
```
