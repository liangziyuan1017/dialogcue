---
id: SUM-20260415-1400-database-migration
title: "Conversation Summary: database-migration"
doc_kind: summary
status: accepted
created: 2026-04-15
schema_version: 1
source_ids: ["conversation-042"]
layer: L1
is_summary_of_summary: false
---

# Conversation Summary: Database Migration Planning

## Key Decisions Referenced
- ADR-001: Use PostgreSQL 16 as primary database — confirmed as target
- Decided to use pg_dump for initial migration, logical replication for ongoing sync

## Key Lessons Referenced
- LL-001: Port conflict pattern — allocated port 5432 explicitly in migration config
- LL-002: Stale index after concurrent writes — scheduled migration during maintenance window

## Actions Resolved
- Migration script written at `scripts/migrate-db`
- Rollback plan documented in `docs/operations/rollback-db.md`
- Dry run completed on staging — 42min for 2M rows

## Open Questions
- Should we enable PGQ for event sourcing during migration?
- Timeline for decommissioning old MySQL instance?

---
Generated: 2026-04-15T14:00:00
Source: conversation-042
Layer: L1
