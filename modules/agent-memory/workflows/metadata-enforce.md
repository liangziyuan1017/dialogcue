# Metadata Enforce Workflow

> **Skill**: `skills/metadata-enforce/SKILL.md`
> **Purpose**: Validate document frontmatter and metadata compliance across durable memory files.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `discover-docs` | `scripts/discover-docs.py` | Scan for all durable memory documents under a path |
| `frontmatter-lint` | `scripts/frontmatter-lint.py` | Validate frontmatter against `schemas/frontmatter.schema.yaml` |
| `knowledge-validate` | `scripts/knowledge-validate.py` | Validate optional `knowledge:` block against `schemas/knowledge-object.schema.yaml` |
| `lint-report` | `scripts/lint-report.py` | Produce a human-readable compliance report |

## Execution Order

1. **Accept target**: Accept a path (file or directory). Default: `docs/` in host project root.
   ```
   scripts/discover-docs.py --root <TARGET_PATH>
   ```
   → Output: list of all `.md` files under the target.

2. **Validate frontmatter for each document**:
   ```
   scripts/frontmatter-lint.py --file <DOC_PATH>
   ```
   → Run against every discovered file.
   → Check required fields: `id`, `title`, `doc_kind`, `created`, `schema_version`.
   → Check `doc_kind` is in enum: `decision | lesson | spec | plan | discussion | research | bug-report | review | note | summary`.
   → Check `status` (if present) is in enum: `draft | review | accepted | deprecated | superseded | archived`.
   → Rule: `rules.md §8` — `schema_version` must be present and parseable.

3. **Validate knowledge block** (if present):
   ```
   scripts/knowledge-validate.py --file <DOC_PATH>
   ```
   → Check `authority` in: `observed | candidate | validated | constitutional`.
   → Check `activation` in: `query | scoped | always_on | backstop`.
   → Check `knowledge.status` in: `active | review | invalidated | archived`.
   → Check `exportability` in: `private | project_only | generalized`.
   → Rule: `rules.md §3` — `authority`, `activation`, and `status` are orthogonal axes.

4. **Collect violations per document**:
   ```
   scripts/lint-report.py --results <PER_FILE_RESULTS>
   ```
   → Aggregates violations from frontmatter-lint and knowledge-validate.
   → Violation categories:
     - Missing required fields → `MISSING: <field>`.
     - Invalid enum value → `INVALID: <field> = "<value>" (use: <enum_values>)`.
     - Missing `schema_version` → `MISSING: schema_version`.
     - `schema_version` mismatch → `VERSION_MISMATCH: doc=<X>, module=<Y>`.

5. **Generate compliance report**:
   ```
   scripts/lint-report.py --results <RESULTS_JSON>
   ```
   → Output: per-file breakdown + summary counts.
   ```
   === Metadata Compliance Report ===
   Files checked: 42
   Passed: 39
   Violations: 3
   
   Violations:
   - docs/decisions/ADR-003.md: MISSING: schema_version
   - docs/decisions/ADR-007.md: INVALID: status = "proposed" (use: draft|review|accepted|deprecated|superseded|archived)
   - docs/lessons/LL-012.md: MISSING: created
   ```

6. **Exit code**:
   - 0: all documents pass (no violations).
   - 1: one or more violations found.

## Success Conditions

- All discovered documents have valid required fields.
- All `doc_kind`, `status`, and `knowledge.*` values are in their respective enums.
- `schema_version` is present and matches module expectations.

## Failure Conditions

- Any required field missing → exit code 1, report per file.
- Any enum value invalid → exit code 1, report expected values.
- No `.md` files found at target path → exit code 0, report `"no documents found"` (not an error).

## Skip Conditions

- `doc_kind` values not in the enum are reported as violations but the doc is not rejected for indexing.
- Missing optional fields (`feature_ids`, `topics`, `updated`, `related`) are noted as warnings, not violations.
- Empty `knowledge:` block is valid — the block is optional.

## Next Step

Metadata enforcement is a terminal capability — it produces a report and does not chain to another skill. If violations are found:

| Violation Type | Recommended Action |
|---|---|
| Missing required field | Manually add the field to the document |
| Invalid enum value | Correct the value to a valid enum member |
| Missing schema_version | Add `schema_version: 1` to frontmatter |
| Schema version mismatch | Run migration script or update document |

## Document Sync Rule

Metadata enforcement is read-only. No documents are created or modified. The compliance report is written to stdout only.

## Iron Laws

- Required fields (`id`, `title`, `doc_kind`, `created`, `schema_version`) are non-negotiable — documents missing any of these are in violation.
- Enum values are closed sets — no custom values are permitted for `doc_kind`, `status`, `authority`, `activation`, `knowledge.status`, or `exportability`.
- `schema_version` must be present and parseable as an integer.

## Anti-patterns

- **Auto-fixing violations**: Metadata enforcement reports violations but does not modify documents. Fixes must be applied manually to preserve auditability.
- **Treating warnings as violations**: Missing optional fields (`feature_ids`, `topics`, `updated`) are warnings, not violations. Do not fail the build on warnings.

## Test References

| Test | Path |
|---|---|
| validate_frontmatter | `tests/test_validate_frontmatter.py` |
| validate_knowledge_block | `tests/test_validate_frontmatter.py` |

## Reproducible Example

```bash
# Validate entire docs/ directory
scripts/discover-docs.py --root docs/
# Expected: returns list of all .md files

scripts/frontmatter-lint.py --file docs/decisions/ADR-003.md
# Expected: "MISSING: schema_version"

scripts/frontmatter-lint.py --file docs/decisions/ADR-007.md
# Expected: "INVALID: status = proposed (use: draft|review|accepted|deprecated|superseded|archived)"

scripts/frontmatter-lint.py --file docs/lessons/LL-042.md
# Expected: "valid"

scripts/knowledge-validate.py --file docs/lessons/LL-042.md
# Expected: "knowledge block: authority=observed, activation=query, status=active — valid"

scripts/lint-report.py --results '[{"file":"ADR-003","violations":["MISSING: schema_version"]},{"file":"ADR-007","violations":["INVALID: status"]},{"file":"LL-042","violations":[]}]'
# Expected: "Files checked: 3, Passed: 1, Violations: 2"

# Single file validation
scripts/frontmatter-lint.py --file docs/lessons/LL-042.md
# Expected: "valid"
```
