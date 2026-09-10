---
REMOVED_FIELD_id: ADR-027
title: "DB concurrency: threadpool on psycopg2 (F012 Phase B), then asyncpg runtime migration (F013, merged)"
doc_kind: decision
feature_ids: [F012, F013]
topics: [architecture, db, concurrency, async]
status: superseded
created: 2026-07-01
updated: 2026-07-02
schema_version: 1
knowledge:
  authority: validated
  activation: scoped
  status: active
  exportability: project_only
  source_ids: [F012, F013]
  review_cycle_days: 90
---

# ADR-027: DB concurrency — threadpool on psycopg2 (F012 Phase B), then asyncpg runtime migration (F013, merged)

## What

F012 Phase B fixed the single-shared-connection outage risk by introducing a
`psycopg2.pool.ThreadedConnectionPool` and running DB work in FastAPI's
`run_in_threadpool`. F013 then replaced the runtime DB driver with `asyncpg`,
making all runtime DB methods async and eliminating thread overhead. The
threadpool was an interim fix; asyncpg is the final runtime architecture.

## Why

The single synchronous `psycopg2` connection in `SentenceDB` was shared across async FastAPI/SocketIO handlers — the top production outage risk in the F012
review. The threadpool fix closed the concurrency hole with minimal scope and no driver rewrite. `asyncpg` is faster (no thread overhead, binary protocol for vector data) but was a substantially larger change that deserved its own design scrutiny, migration plan, and review gate — bundling it into F012 would have ballooned scope and risk.

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Migrate to asyncpg inside F012 | Too large; rewrites db.py + all call sites; merges two risks into one PR; violates KD-2 (each phase = separate PR) |
| Keep single connection + add a lock | Does not solve the async-blocking problem; serializes all DB access → latency collapse under load |
| Switch to SQLAlchemy async | Even larger scope; introduces an ORM the project does not currently use |
| Keep threadpool as permanent solution | Thread overhead remains; 10-thread ceiling under high concurrency; context switches on every DB call |

## Resolution

- **F012 Phase B** (threadpool): merged to main as interim fix — `ThreadedConnectionPool` + `run_in_threadpool` offload.
- **F013** (asyncpg): merged to main 2026-07-02 — `AsyncSentenceDB` wired into `server.py`, `recommend()`, `extract_state()`, `debug.py` all async. `run_in_threadpool` removed from runtime. `psycopg2` retained only for build-time (`build_tree_and_db.py`).
- **Result**: 3.2× throughput on vector search hot path; zero thread exhaustion under 60 concurrent requests; no `InterfaceError`.

## Next Action

- [x] F012 Phase B: implement ThreadedConnectionPool + threadpool offload — **done, merged to main**
- [x] F013 async driver: `AsyncSentenceDB` (asyncpg) + tests written — **done**
- [x] F013 cutover: wire `AsyncSentenceDB` into `server.py`/`debug.py`, declare `asyncpg` in `pyproject.toml` — **done, merged to main (hard cutover, no feature flag)**
- [x] F013 validation: AC-4/5/7/9 verified (load test, latency benchmark, build-time regression, pool reconnect) — **done**

---

## Revision History

| Date | Change | Author |
|---|---|---|
| 2026-07-01 | Initial draft (Design Gate, F012) | agent |
| 2026-07-01 | Phase B merged to main; Next Action #1 complete | agent |
| 2026-07-02 | F013 async driver module + tests written | agent |
| 2026-07-02 | F013 merged to main — asyncpg is the runtime driver; all ACs verified; ADR status → superseded | agent |
