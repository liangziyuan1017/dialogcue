---
id: ADR-027
title: "F012 DB concurrency: threadpool on psycopg2 now, asyncpg as separate feature"
doc_kind: decision
feature_ids: [F012]
topics: [architecture, db, concurrency, async]
status: accepted
created: 2026-07-01
updated: 2026-07-01
schema_version: 1
knowledge:
  authority: validated
  activation: scoped
  status: active
  exportability: project_only
  source_ids: [F012]
  review_cycle_days: 90
---

# ADR-027: F012 DB concurrency — threadpool on psycopg2 now, asyncpg as separate feature

## What

F012 Phase B will fix the single-shared-connection outage risk by introducing a
`psycopg2.pool.ThreadedConnectionPool` and running DB work in FastAPI's
`run_in_threadpool`. A native `asyncpg` migration is **deferred to a separate
feature** (F013 candidate) with its own doc + ADR, because it requires rewriting
`db.py` and every call site.

## Why

The single synchronous `psycopg2` connection in `SentenceDB` is shared across
async FastAPI/SocketIO handlers — the top production outage risk in the F012
review. The threadpool fix closes the concurrency hole with minimal scope and no
driver rewrite. `asyncpg` would be faster (no thread overhead) but is a
substantially larger change that deserves its own design scrutiny, migration
plan, and review gate — bundling it into F012 would balloon scope and risk.

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Migrate to asyncpg inside F012 | Too large; rewrites db.py + all call sites; merges two risks into one PR; violates KD-2 (each phase = separate PR) |
| Keep single connection + add a lock | Does not solve the async-blocking problem; serializes all DB access → latency collapse under load |
| Switch to SQLAlchemy async | Even larger scope; introduces an ORM the project does not currently use |

## Open Questions

- [ ] F013 (asyncpg) kickoff — who owns, when? (defer until F012 Phase B merged + observed in prod)

## Next Action

- [ ] F012 Phase B: implement ThreadedConnectionPool + threadpool offload
- [ ] After Phase B merges and runs in prod, open F013 for asyncpg migration

---

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-07-01 | Initial draft (Design Gate, F012) | agent |
