# Memory Prune Workflow

> **Skill**: `skills/memory-prune/SKILL.md`
> **Purpose**: Prune, merge, or deprecate stale durable memory without destructive deletion.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `entropy-audit` | `scripts/entropy-audit.py` | Scan for stale, duplicate, or superseded knowledge |
| `tombstone-create` | `scripts/tombstone-create.py` | Create a tombstone record for a deprecated entry |
| `merge-propose` | `scripts/merge-propose.py` | Propose a merge of two entries and produce the merged document |
| `write-durable` | `scripts/write-durable.py` | Write merged entry or update originals with `replaced_by` |
| `prune-report` | `scripts/prune-report.py` | Produce a prune action summary |
| `index-rebuild` | `scripts/index-rebuild.py` | Trigger full reindex after prune operations |

## Execution Order

1. **Run entropy audit**:
   ```
   scripts/entropy-audit.py --root docs/
   ```
   → Output: list of flagged entries with reasons.
   - `stale`: `review_cycle_days` (default 90) elapsed since `last_activated`.
   - `superseded`: `status: active` but `superseded_by` is non-empty.
   - `unused`: `activation_count: 0` after 30 days.
   - `duplicate_candidates`: two entries with matching `topic_key` and overlapping content.
   → Rule: `rules.md §6` — tombstone, never delete. 90-day retention.

2. **Classify actions**: For each flagged entry, determine the action:
   ```
   scripts/entropy-audit.py --root docs/ --classify-actions
   ```
   → Returns each flagged entry with its recommended action:
   | Flag | Action |
   |---|---|
   | `stale` | Review → tombstone or keep with updated `review_cycle_days` |
   | `superseded` | Document `status: superseded` + `knowledge.status: archived` |
   | `unused` | Set `activation: backstop` (preserved, not prominent) |
   | `duplicate_candidates` | Propose merge |

3. **For stale entries**:
   ```
   scripts/tombstone-create.py --id <DOC_ID> --reason "<REASON>" --retention-days 90
   ```
   → Creates tombstone: `.agent-memory/tombstones/<DOC_ID>.tombstone.yaml`.
   → Tombstone includes: `id`, `tombstoned_at`, `reason`, `retain_until`, `original_hash`.
   → Original document preserved; document `status` set to `archived`.
   → Rule: `rules.md §6` — 90-day retention before physical deletion.

4. **For superseded entries**:
   ```
   scripts/write-durable.py --path docs/<path>/<ID>.md --update-frontmatter '{"status":"superseded","replaced_by":"<NEWER_ID>"}'
   ```
   → Document remains in index with `status: superseded`.
   → If `knowledge:` block exists: set `knowledge.status: archived`.
   → Rule: `rules.md §3` — superseded entries point to replacement via `replaced_by`.

5. **For unused entries**:
   ```
   scripts/write-durable.py --path docs/<path>/<ID>.md --update-knowledge '{"activation":"backstop"}'
   ```
   → Entry stays searchable but demoted in default ranking.
   → Rule: `rules.md §3` — `backstop` means preserved but not prominent.

6. **For duplicate candidates** (merge proposal):
   ```
   scripts/merge-propose.py --source1 <ID_1> --source2 <ID_2>
   ```
   → Checks:
   - Both entries have the same `topic_key`.
   - Content overlap exceeds threshold.
   → Produces merged document with:
   - Combined `source_ids` from both originals.
   - New ID allocated.
   - Both originals preserved with `status: superseded` + `replaced_by: <MERGE_ID>`.
   → Rule: `rules.md §6` — no information loss; all `source_ids` preserved.

7. **Validate before execution** (`rules.md §6`):
   ```
   scripts/rule-check.py --rules compression --against <PROPOSED_ACTIONS>
   ```
   → Validates:
     - No information loss (all `source_ids` preserved).
     - No active decisions removed (check `status`).
     - Tombstones created for all removed entries.
     - Index consistency maintained.

8. **Generate prune report**:
   ```
   scripts/prune-report.py --actions <ACTIONS_JSON>
   ```
   → Output:
   ```
   === Prune Report ===
   Stale flagged: 3 → 3 tombstoned (retain until 2026-08-23)
   Superseded: 1 → status updated to superseded
   Unused: 2 → activation set to backstop
   Merges proposed: 1 → ADR-003 + ADR-007 → ADR-018
   Deletions: 0
   Information loss: 0
   ```

9. **Trigger full reindex**:
   ```
   scripts/index-rebuild.py --scope full
   ```
   → Full rebuild required after prune operations (document set changed).
   → Rule: `rules.md §1` — explicit reindex after durable writes.

## Success Conditions

- All flagged entries receive a non-destructive action (tombstone, supersede, backstop, or merge).
- No active decisions removed.
- All `source_ids` preserved in merges.
- Tombstones created with 90-day retention.
- Full reindex succeeds.

## Failure Conditions

- Attempted hard delete → BLOCKED, exit code 1.
- Merge would lose `source_ids` → BLOCKED, exit code 1.
- Tombstone creation fails (disk error) → exit code 1.
- Entropy audit fails to scan → exit code 1.

## Non-Destructive Rules

All prune actions comply with `rules.md §6`. Key invariants:
- Tombstone, never delete
- 90-day retention before physical deletion
- Source traceability preserved in merges
- Deprecated/superseded documents remain searchable

## Next Step

After a successful prune:

→ `memory-index` — full reindex is triggered automatically (step 9). This is required because the document set has changed (tombstones, supersedes, merges).

If merges were proposed:
→ Review the merged document for accuracy before accepting.
→ Run `governance-review` on the merged document to verify compliance.

## Document Sync Rule

After prune operations:
1. Tombstone records are written to `.agent-memory/tombstones/<ID>.tombstone.yaml`.
2. Superseded documents are updated with `status: superseded` and `replaced_by: <NEWER_ID>`.
3. Merged documents are written as new entries; originals are marked `superseded`.
4. Backstop demotions update `knowledge.activation: backstop` in the document frontmatter.
5. Full reindex updates `.agent-memory/index.json`.
6. Original documents are never deleted — they remain searchable with updated status.

## Iron Laws

- **Tombstone, never delete**: No knowledge object is ever hard-deleted. Tombstones with 90-day retention are the only removal mechanism.
- **No information loss in merges**: All `source_ids` from both originals must be preserved in the merged document.
- **No active decisions removed**: Prune must not remove or archive decisions with `status: accepted` or `status: draft`.
- **90-day retention**: Tombstoned documents are retained for at least 90 days before physical deletion.

## Anti-patterns

- **Hard delete**: Never `rm` a durable document. Always use `tombstone-create`. Hard deletes violate auditability.
- **Merge without source traceability**: A merge that does not preserve `source_ids` from both originals loses provenance. Reject.
- **Pruning active knowledge**: Setting `status: archived` on an `accepted` decision without a replacement is a violation. Active knowledge must be superseded, not just archived.
- **Prune without reindex**: After any prune operation, a full reindex is mandatory. The document set has changed; the index must reflect the new state.

## Test References

| Test | Path |
|---|---|
| prune_memory | `tests/test_prune_memory.py` |
| prune_nondestructive | `tests/test_prune_memory.py` |

## Reproducible Example

```bash
# Run entropy audit
scripts/entropy-audit.py --root docs/
# Expected: returns flagged entries list

# Stale entry → tombstone
scripts/tombstone-create.py --id ADR-002 --reason "review_cycle_days exceeded (120 days)" --retention-days 90
# Expected: "tombstone created: .agent-memory/tombstones/ADR-002.tombstone.yaml, retain until 2026-08-23"

# Superseded entry
scripts/write-durable.py --path docs/decisions/ADR-003.md --update-frontmatter '{"status":"superseded","replaced_by":"ADR-018"}'
# Expected: "updated: docs/decisions/ADR-003.md"

# Unused entry → backstop
scripts/write-durable.py --path docs/lessons/LL-005.md --update-knowledge '{"activation":"backstop"}'
# Expected: "updated knowledge.activation: backstop"

# Merge two entries
scripts/merge-propose.py --source1 ADR-003 --source2 ADR-007
# Expected: merged doc created as ADR-018, originals updated with replaced_by: ADR-018

# Prune report
scripts/prune-report.py --actions '[
  {"type":"tombstone","id":"ADR-002","reason":"stale"},
  {"type":"supersede","id":"ADR-003","replaced_by":"ADR-018"},
  {"type":"backstop","id":"LL-005","reason":"unused"},
  {"type":"merge","ids":["ADR-003","ADR-007"],"result":"ADR-018"}
]'
# Expected: "3 tombstoned, 1 superseded, 1 backstop, 1 merged, 0 deletions, 0 information loss"

# Full reindex
scripts/index-rebuild.py --scope full
# Expected: "42 docs indexed, 0 hash conflicts"
```
