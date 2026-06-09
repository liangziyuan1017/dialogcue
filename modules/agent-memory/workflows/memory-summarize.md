# Memory Summarize Workflow

> **Skill**: `skills/memory-summarize/SKILL.md`
> **Purpose**: Generate durable conversation summaries from stable source material.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `summarize-check-eligibility` | `scripts/summarize-check-eligibility.py` | Check if source material meets L1 summarization thresholds |
| `summarize-generate` | `scripts/summarize-generate.py` | Generate a durable summary segment from source material |
| `id-allocate` | `scripts/id-allocate.py` | Allocate summary ID (SUM-YYYYMMDD-HHMM-<slug>) |
| `write-durable` | `scripts/write-durable.py` | Write summary segment to `docs/summaries/` |
| `index-rebuild` | `scripts/index-rebuild.py` | Trigger incremental reindex |
| `frontmatter-lint` | `scripts/frontmatter-lint.py` | Validate summary frontmatter |

## Execution Order

1. **Guard: no-summary-of-summary** (`rules.md §7`):
   ```
   scripts/summarize-check-eligibility.py --input <SOURCE> --check-is-summary
   ```
   → If source material is already a summary (has `doc_kind: summary` or `layer: L1` in metadata):
   → **REJECT immediately**: `VIOLATION: rules.md §7 — no-summary-of-summary`.
   → Exit code 1. Do not proceed.

2. **Check eligibility thresholds**:
   ```
   scripts/summarize-check-eligibility.py --input <SOURCE> --quiet-window 10 --min-messages 20
   ```
   → Checks:
   - `quiet_window_min`: At least 10 minutes since last message in source material.
   - `min_messages`: At least 20 messages in the source material.
   → If thresholds not met: exit code 0, report `"not eligible: <reason>"`.
   → Rule: `rules.md §2` — only stable, completed material enters durable memory.

3. **Allocate summary ID**:
   ```
   scripts/id-allocate.py --kind SUM --slug "<SLUG>"
   ```
   → Output: `SUM-20260525-1430-<slug>`.

4. **Assemble frontmatter**:
   ```yaml
   id: <ALLOCATED_ID>
   title: "Conversation Summary: <SLUG>"
   doc_kind: summary
   status: draft
   created: <TODAY>
   schema_version: 1
   source_ids: [<SOURCE_IDS>]
   layer: L1
   is_summary_of_summary: false
   ```

5. **Validate frontmatter**:
   ```
   scripts/frontmatter-lint.py --input <FRONTMATTER_YAML>
   ```
   → `is_summary_of_summary` must be `false`.
   → `source_ids` must reference original source material, not other summaries.

6. **Generate summary segment**:
   ```
   scripts/summarize-generate.py --source <SOURCE_MATERIAL> --layer L1 --output <TEMP_PATH>
   ```
   → Produces:
   - Key decisions referenced
   - Key lessons referenced
   - Action items resolved
   - Open questions remaining
   - Source material provenance
   → Rule: `rules.md §7` — summaries are append-only; no summary-of-summary.

7. **Write summary document** (append-first):
   ```
   scripts/write-durable.py --path docs/summaries/<ID>.md --content <ASSEMBLED_DOC>
   ```

8. **Trigger incremental reindex**:
   ```
   scripts/index-rebuild.py --scope incremental --files docs/summaries/<ID>.md
   ```

## Success Conditions

- Source material passes `is_summary_of_summary: false` guard.
- Eligibility thresholds met (quiet window + message count).
- Summary written to `docs/summaries/` with valid frontmatter.
- `is_summary_of_summary: false` is enforced in frontmatter.

## Failure Conditions

- Source is already a summary → exit code 1, VIOLATION.
- Eligibility thresholds not met → exit code 0, `"not eligible"`.
- `frontmatter-lint` reports violations → exit code 1.
- `summarize-generate` fails → exit code 1.

## Invariants (from `rules.md §7`)

- **Append-only**: Summaries are appended, never overwritten.
- **No summary-of-summary**: A summary cannot be the input to `summarize-generate`.
- **Provenance**: Every summary links back to its source material via `source_ids`.
- **Layer marking**: First summarization pass = L1. No L2 (that would be summary-of-summary).

## Next Step

After a summary is successfully written:

→ `memory-index` — incremental reindex is triggered automatically (step 8). If reindex fails, the summary is still written; run `memory-index --scope incremental` manually.

## Document Sync Rule

After writing a summary:
1. The new document is written to `docs/summaries/<ID>.md`.
2. Incremental reindex updates `.agent-memory/index.json`.
3. The `source_ids` in the summary frontmatter link back to the original conversation or documents.

## Iron Laws

- **No summary-of-summary**: A summary must never be the input to `summarize-generate`. This is enforced by `is_summary_of_summary: false` in frontmatter and the eligibility guard (step 1).
- **Append-only**: Summaries are appended, never overwritten.
- **Provenance required**: Every summary must include `source_ids` referencing the original source material.

## Anti-patterns

- **Summarizing a summary**: Re-summarizing an L1 summary to produce an "L2" is explicitly forbidden by rules.md §7. Reject immediately.
- **Summarizing active conversations**: The quiet window threshold exists to ensure only stable, completed material enters durable memory. Do not bypass it.
- **Summary without source_ids**: A summary that does not link back to its source material loses provenance. Reject.

## Test References

| Test | Path |
|---|---|
| summarize_conversation | `tests/test_summarize_conversation.py` |
| summarize_eligibility | `tests/test_summarize_conversation.py` |

## Reproducible Example

```bash
# Eligible conversation
scripts/summarize-check-eligibility.py --input fixtures/conversation-42.txt --check-is-summary
# Expected: "not a summary — OK"

scripts/summarize-check-eligibility.py --input fixtures/conversation-42.txt --quiet-window 10 --min-messages 20
# Expected: "eligible: 40 messages, 15 min quiet window"

scripts/id-allocate.py --kind SUM --slug "api-design-discussion"
# Expected: "SUM-20260525-1430-api-design-discussion"

scripts/frontmatter-lint.py --input '
id: SUM-20260525-1430-api-design-discussion
title: "Conversation Summary: api-design-discussion"
doc_kind: summary
status: draft
created: 2026-05-25
schema_version: 1
is_summary_of_summary: false
'
# Expected: "valid"

scripts/summarize-generate.py --source fixtures/conversation-42.txt --layer L1 --output /tmp/summary.md
scripts/write-durable.py --path docs/summaries/SUM-20260525-1430-api-design-discussion.md --content /tmp/summary.md
scripts/index-rebuild.py --scope incremental --files docs/summaries/SUM-20260525-1430-api-design-discussion.md

# Rejected: summary-of-summary
scripts/summarize-check-eligibility.py --input docs/summaries/SUM-20260525-1430-api-design-discussion.md --check-is-summary
# Expected: "REJECTED: rules.md §7 — no-summary-of-summary"
```
