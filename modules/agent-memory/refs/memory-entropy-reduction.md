# Memory Entropy Reduction — Knowledge Lifecycle

> Normalized from clowder-ai F163 (Memory Entropy Reduction).
> Knowledge decays. This defines how to keep it precise.

## The Problem

Memory systems tend to only have "add" mechanisms. Without "subtract," knowledge drifts:
- Stale decisions remain in the index long after they're superseded
- Duplicate lessons describe the same pitfall
- Rules accumulate without pruning, making it hard to find what matters

## The Multi-Axis Solution

Knowledge is not a flat list. Every entry has orthogonal axes that determine its lifecycle:

| Axis | Values | What It Controls |
|------|--------|-----------------|
| `authority` | observed → candidate → validated → constitutional | Whether it's trusted enough to load proactively |
| `activation` | query → scoped → always_on → backstop | When and where it's loaded into agent context |
| `status` | active → review → invalidated → archived | Whether it's current or should be re-evaluated |

## Lifecycle Actions

### Detect Stale
- Flag entries where `review_cycle_days` (default: 90) have elapsed since `last_activated`
- Flag entries where `status: active` but `superseded_by` is non-empty
- Flag entries with `activation_count: 0` after 30 days

### Propose Merge
- Two entries with the same `topic_key` and overlapping content → propose merge
- Merged entry preserves `source_ids` from both originals
- Original entries get document `status: superseded` and `knowledge.status: archived`, with `replaced_by` pointing to the merge

### Validate Entropy Reduction
- Before executing any prune or merge, validate:
  1. No information loss (all `source_ids` preserved)
  2. No active decisions removed (check `status`)
  3. Tombstones created for all removed entries
  4. Index consistency maintained

## Non-Destructive Rules

1. **Tombstone, never delete.** All removals are soft tombstones with audit logs.
2. **90-day retention.** Physical deletion only after tombstone ages past retention period.
3. **Source traceability.** Merged or pruned entries retain link to originals via `source_ids`.
4. **Searchable deprecated.** Deprecated and superseded documents remain in the index with appropriate document status — they're just not in default results.

See also: `rules.md` §4 (Write and Concurrency Rules), §6 (Compression Rules) — the module-level policies that enforce these rules. `schemas/knowledge-object.schema.yaml` → `review_cycle_days`, `stale_after_days`.

## Staleness Thresholds

| Document Type | Review Cycle | Stale After |
|---------------|-------------|-------------|
| ADR (decision) | 90 days | 180 days without review |
| Lesson (LL-XXX) | 180 days | 365 days without activation |
| Feature spec | 30 days (active) | 90 days without update |
| Summary | 30 days | 60 days without source material update |
