# Metadata Contract

> Normalized from clowder-ai ADR-011 (Document Metadata Contract).
> Every document in `docs/` must have YAML frontmatter following this contract.

## Required Fields

```yaml
---
id: ADR-001              # Unique identifier (ADR-XXX, LL-XXX, FXXX, BUG-XXX)
title: "Decision Title"  # One-line summary
doc_kind: decision       # Document type (see enum below)
created: 2026-05-25      # Creation date (YYYY-MM-DD)
schema_version: 1         # Schema version this doc was written against
---
```

## Optional Fields

```yaml
feature_ids: [F001]      # Related feature IDs
topics: [memory, search] # Loose topic tags
status: accepted         # Current status
updated: 2026-05-25      # Last update date
related: [ADR-005]       # Related document IDs
supersedes: [ADR-003]    # What this document replaces
replaced_by: ADR-007     # What replaces this document
```

## `doc_kind` Enum

| Value | Purpose | Directory |
|-------|---------|-----------|
| `decision` | Architecture Decision Record | `docs/decisions/` |
| `lesson` | Lesson learned | `docs/lessons/` |
| `spec` | Feature specification | `docs/features/` |
| `plan` | Implementation plan | `docs/features/` |
| `discussion` | Discussion record | `docs/discussions/` |
| `research` | Technical research | `docs/research/` |
| `bug-report` | Bug report | `docs/bugs/` |
| `review` | Review request or response | `docs/reviews/` |
| `note` | General note | `docs/notes/` |
| `summary` | Conversation or project summary | `docs/summaries/` |

## `status` Enum

This is the **document workflow status** in frontmatter, not the `knowledge.status` lifecycle axis.

| Value | Meaning |
|-------|---------|
| `draft` | Work in progress — not ready for review |
| `review` | Under review |
| `accepted` | Accepted and active |
| `deprecated` | No longer current but still searchable |
| `superseded` | Replaced by another document (see `replaced_by`) |
| `archived` | Historical record only |

## Rules

1. `feature_ids` and `topics` enable search. Omit them only if truly irrelevant.
2. `status` does NOT go into general discussion or research docs — only decisions, lessons, specs, and bugs.
3. `schema_version` enables migration. Every doc declares which schema version it was written against.
4. Document `status` is distinct from `knowledge.status`. Do not mix the two layers.
5. The metadata contract is enforced by the `metadata-enforce` skill.
