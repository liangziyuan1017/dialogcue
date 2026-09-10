---
REMOVED_FIELD_id: LL-004
title: "Plan docs drifted from shipped feature IDs, causing silent renumber and dead links"
doc_kind: lesson
feature_ids: [F007, F007b, F008, F009, F010]
topics: [doc-drift, feature-numbering, plan-consistency, cross-references]
status: accepted
created: 2026-06-26
schema_version: 1
pitfall: "The original plan doc (plan_feature_base.md, now folded into docs/ROADMAP.md) defined F007–F009 but the work was shipped under F010–F013; the plan was never updated, so two contradictory dependency graphs coexisted and ROADMAP/feature docs/ADRs cross-referenced IDs that no longer matched"
root_cause: "Feature IDs were renumbered during implementation without back-propagating the change to the plan doc, ROADMAP, source labels, and ADR feature_ids. No gate checks that ROADMAP dependency graph == feature doc depends_on"
trigger_conditions: "When features are re-ID'd after planning, or when a plan doc is left as a fossil while implementation proceeds under different IDs"
fix: "Renumbered F010–F013 → F007/F007b/F008/F009 (scope-mapped), renamed files, updated all frontmatter/depends_on/ROADMAP/ADR feature_ids/cross-links. Then renumbered F014 → F010 to fill the freed ID, and closed the ADR-024 gap by shifting ADR-025→024, ADR-026→025"
guard: "After any feature renumber or plan update, run a consistency pass: (1) every ROADMAP row link resolves, (2) every feature doc REMOVED_FIELD_id/name/status matches ROADMAP, (3) every depends_on resolves to an existing feature REMOVED_FIELD_id, (4) every ADR ref resolves, (5) every relative .md link resolves, (6) ROADMAP dependency graph matches the union of feature doc depends_on. Treat a stale plan doc as a bug, not a historical artifact"
source_anchor: ["docs/ROADMAP.md dependency graph", "docs/features/F007-infra-layer.md", "docs/decisions/ADR-024-embedding-architecture.md"]
---

# Plan Docs Drifted From Shipped Feature IDs

## Pitfall

The original plan doc (`plan_feature_base.md`, since folded into `docs/ROADMAP.md`) defined features F007 (Scaling Architecture Design), F008 (State Extraction), F009 (REST API) in its dependency graph. The actual implementation was shipped under IDs F010 (Infrastructure Layer), F011 (Vector Retrieval Integration), F012 (State Extraction), F013 (REST API + Socket.IO). The plan doc was never updated, so:

- Two contradictory dependency graphs coexisted (plan vs. feature docs).
- `docs/ROADMAP.md` jumped F006 → F010 with no F007–F009 rows.
- Feature docs, ADR `feature_ids`, and cross-links all referenced F010–F013.
- `source: stepwise_modification.md` (now `docs/features/F007-F009-implementation-steps.md`) was a dead link (file missing at the time).
- F007's scaling-analysis content was orphaned (no successor feature doc).

## Root Cause

Feature IDs were renumbered during implementation without back-propagating the change to the plan doc, ROADMAP, source labels, and ADR `feature_ids`. There was no gate checking that the dependency graph == ROADMAP rows == feature doc `depends_on`.

## Trigger Conditions

When features are re-ID'd after planning, or when a plan doc is left as a fossil while implementation proceeds under different IDs. Also when a sub-feature (F007b) is introduced without a plan-doc section.

## Fix

- Scope-mapped and renumbered F010→F007, F011→F007b, F012→F008, F013→F009.
- Relocated the orphaned F007 scaling content into `F007-infra-layer.md` (## Scaling Path).
- Reconciled the dependency graph (now in `docs/ROADMAP.md`) + F007/F008/F009 section definitions to match shipped scopes; added F007b section + Edit-Sequence→feature-ID mapping note (now in `F007-F009-implementation-steps.md`).
- Renumbered F014 → F010 to fill the freed ID.
- Closed the ADR-024 gap by shifting ADR-025→024 (embedding) and ADR-026→025 (UI).
- Fixed all broken relative links (bare `implementation-plan.md`, `../../decisions/` one level too deep, `../../plan.md`).
- Normalized all feature doc frontmatter to `REMOVED_FIELD_id`/`name`/`status` schema.

## Guard

After any feature renumber or plan update, run a consistency pass:

1. Every ROADMAP row link resolves to a file.
2. Every feature doc `REMOVED_FIELD_id`/`name`/`status` matches its ROADMAP row.
3. Every `depends_on` resolves to an existing feature `REMOVED_FIELD_id`.
4. Every ADR reference resolves to an existing ADR file.
5. Every relative `.md` link resolves.
6. `docs/ROADMAP.md` dependency graph matches the union of feature doc `depends_on`.

Treat a stale plan doc as a bug, not a historical artifact. If renumbering is needed, update the plan doc in the same commit.

## Source Anchors

- `docs/ROADMAP.md` — dependency graph (now reconciled) + 12 rows, all resolve
- `docs/features/F007-infra-layer.md` — renumbered from F010
- `docs/decisions/ADR-024-embedding-architecture.md` — renumbered from ADR-025
