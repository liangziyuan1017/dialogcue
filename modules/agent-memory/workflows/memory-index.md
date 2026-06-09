# Memory Index Workflow

> **Skill**: `skills/memory-index/SKILL.md`
> **Purpose**: Build or rebuild the searchable memory index from durable project documents.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `discover-docs` | `scripts/discover-docs.py` | Scan for durable memory documents since last index |
| `content-hash` | `scripts/content-hash.py` | Compute content hash for each document to detect changes |
| `index-rebuild` | `scripts/index-rebuild.py` | Rebuild the searchable memory index (full or incremental) |
| `index-report` | `scripts/index-report.py` | Produce a human-readable rebuild summary |

## Execution Order

1. **Determine scope**: Accept `--scope full` or `--scope incremental` (default: `incremental`).
   - `full`: Rebuild the entire index from scratch.
   - `incremental`: Only re-index documents whose content hash changed since last build.

2. **Acquire index lock**:
   ```
   scripts/index-rebuild.py --acquire-lock
   ```
   → Rule: `rules.md §4` — index rebuilds are serialized per project via `.agent-memory/locks/index-rebuild.lock`.
   → If lock cannot be acquired within 30s, report conflict and exit code 2.

3. **Discover changed documents** (incremental only):
   ```
   scripts/discover-docs.py --changed-since <LAST_INDEX_TIMESTAMP>
   ```
   → Output: list of doc paths with changed content hashes.
   → For `full` scope: `scripts/discover-docs.py --all` instead.

   ```
   scripts/content-hash.py --files <CHANGED_FILES>
   ```
   → Output: file→hash mapping for change detection.
   → Used by `index-rebuild --scope incremental` to skip unchanged documents.

4. **Rebuild index**:
   ```
   scripts/index-rebuild.py --scope <SCOPE> --files <FILE_LIST>
   ```
   → Output: number of docs indexed, hash conflicts detected, index location (`.agent-memory/`).
   → Rule: `rules.md §1` — index is a rebuildable artifact; documents are the source of truth.

5. **Resolve hash conflicts**: If two documents produce the same content hash:
   - Report both doc paths in the rebuild report.
   - Index both documents separately (hash collision does not imply duplicate content).
   - Mark index entry with `hash_collision: true`.

6. **Release lock and report**:
   ```
   scripts/index-report.py --indexed <COUNT> --skipped <COUNT> --conflicts <COUNT>
   ```
   → Output: rebuild summary written to stdout.
   → Release `.agent-memory/locks/index-rebuild.lock`.

7. **Handle concurrent writes**: If documents were mutated during the rebuild:
   - Mark index as `stale_since: <TIMESTAMP>`.
   - Return exit code 0 with warning: `"3 docs mutated during rebuild; re-run incremental to catch up."`
   → Rule: `rules.md §4` — rebuild marks itself stale and reruns once writes settle.

## Success Conditions

- Lock acquired within timeout.
- `index-rebuild` produces a consistent index artifact.
- Index location (`.agent-memory/`) is writable.
- Report is generated with accurate counts.

## Failure Conditions

- Lock acquisition timeout (30s) → exit code 2, report `"index-rebuild.lock held by another process"`.
- Index destination is not writable → exit code 1, report disk error.
- `discover-docs` fails to scan → exit code 1, report scan error.

## Performance

- Incremental rebuild must not re-index unchanged documents.
- Full rebuild is acceptable as O(n) where n = document count.
- Lock is held only during index write, not during discovery or validation.

## Next Step

After a successful index rebuild:

→ `memory-search` — the updated index is now available for retrieval.

If the rebuild detected hash conflicts:
→ Review the conflicting documents for potential duplicates.
→ If duplicates are confirmed, route to `memory-prune --action merge`.

## Document Sync Rule

After index rebuild:
1. The index artifact is written to `.agent-memory/index.json`.
2. Content hashes are updated in `.agent-memory/content-hashes.json`.
3. The lock file `.agent-memory/locks/index-rebuild.lock` is released.
4. No durable documents (docs/decisions/, docs/lessons/, docs/summaries/) are modified.

## Iron Laws

- Index rebuilds are serialized — only one rebuild may run at a time per project.
- Documents are the source of truth; the index is a rebuildable artifact. If the index is corrupt, rebuild it — do not attempt manual repair.
- Incremental rebuild must not re-index unchanged documents.

## Anti-patterns

- **Rebuilding on every search**: Index rebuilds are O(n). Only rebuild when documents have changed, not before every search.
- **Manual index editing**: Never edit `.agent-memory/index.json` by hand. Always use `index-rebuild`.
- **Holding the lock during discovery**: The lock must be held only during index write, not during document discovery or validation.

## Test References

| Test | Path |
|---|---|
| rebuild_index | `tests/test_rebuild_index.py` |
| incremental_rebuild | `tests/test_rebuild_index.py` |

## Reproducible Example

```bash
# Full rebuild
scripts/index-rebuild.py --acquire-lock
scripts/discover-docs.py --all
scripts/index-rebuild.py --scope full --files docs/decisions/*.md docs/lessons/*.md
scripts/index-report.py --indexed 42 --skipped 0 --conflicts 0
# Expected: "42 docs indexed, 0 hash conflicts, last_full_rebuild: 2026-05-25T10:00:00Z"

# Incremental rebuild after 2 files changed
scripts/index-rebuild.py --acquire-lock
scripts/discover-docs.py --changed-since 2026-05-25T09:00:00Z
# Expected: returns 2 file paths
scripts/index-rebuild.py --scope incremental --files docs/decisions/ADR-015.md docs/lessons/LL-050.md
scripts/index-report.py --indexed 2 --skipped 40 --conflicts 0
# Expected: "2 docs re-indexed, 40 unchanged, last_incremental_rebuild: 2026-05-25T10:05:00Z"
```
