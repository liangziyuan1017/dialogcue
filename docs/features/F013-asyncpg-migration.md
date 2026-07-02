---
id: F013
name: asyncpg Migration
status: developing
owner: agent
related_features: [F007, F012]
topics: [db, concurrency, async, asyncpg, performance]
doc_kind: spec
created: 2026-07-01
updated: 2026-07-01
---

# F013: asyncpg Migration

> **Status**: draft | **Owner**: agent | **Priority**: P1
>
> **Origin**: ADR-027 KD-6 — split from F012 Phase B to keep scope bounded.

## Why

F012 Phase B replaced the single shared `psycopg2` connection with a `ThreadedConnectionPool` + `run_in_threadpool` offload. This closes the concurrency hole but retains thread overhead: every DB access blocks a thread and requires a context switch. Under high concurrency (many simultaneous `/recommend` requests), the threadpool becomes a bottleneck — threads are a finite resource and each blocked DB call holds one.

`asyncpg` is a native async PostgreSQL driver. It eliminates thread overhead entirely: DB I/O is coroutine-based, no threads, no context switches, no pool size ceiling tied to thread count. For the hot path (`search_by_nodes`, `get_node_ids_by_signatures`, `keyword_search`, `taxonomy_keyword_search`), this means lower latency and higher throughput under load.

## What

Rewrite `f007_infrastructure/db.py` to use `asyncpg` instead of `psycopg2` + `ThreadedConnectionPool`. All public methods become `async`. Call sites in `server.py` and `debug.py` switch from `run_in_threadpool(sync_call)` to `await async_call()`.

### Scope

- `db.py` — full rewrite: `asyncpg` connection pool, async methods, pgvector async support
- `server.py` — remove `run_in_threadpool` wrappers for DB calls, `await` directly
- `debug.py` — same (debug is sync, so wrap async calls with `asyncio.run` or keep sync fallback)
- `build_tree_and_db.py` — build-time path stays sync (uses `psycopg2` for batch inserts; asyncpg not needed at build time)
- Tests — update all DB tests to use `asyncpg` + `pytest-asyncio`

### Out of Scope

- Build-time pipeline (`whole_pipeline.py`, `build_tree_and_db.py`) — these remain sync with `psycopg2`
- LLM client — already async-compatible via `httpx`; no change needed
- Embedding client — same; no change needed

## Acceptance Criteria

- [ ] AC-1: `db.py` uses `asyncpg` connection pool; no `psycopg2` imports in runtime path
- [ ] AC-2: All `db.py` public methods are `async`; return types unchanged
- [ ] AC-3: `server.py` DB calls use `await` directly (no `run_in_threadpool`)
- [ ] AC-4: N concurrent `/recommend` requests complete with no `InterfaceError` or thread exhaustion
- [ ] AC-5: Latency under load: p99 ≤ 80% of psycopg2+threadpool baseline (measured with `wrk` or `locust`)
- [ ] AC-6: `search_by_nodes`, `get_node_ids_by_signatures`, `keyword_search`, `taxonomy_keyword_search` all return identical results to current implementation
- [ ] AC-7: Build-time path (`build_tree_and_db.py`) still works with `psycopg2` (no regression)
- [ ] AC-8: `pgvector` operations work with `asyncpg` (cosine similarity, embedding insert/select)
- [ ] AC-9: Connection pool reconnects after PG restart (same as F012 AC-B1)
- [ ] AC-10: All existing tests pass (updated for async where needed)

## Dependencies

- **Requires**: F012 Phase B merged and observed in production (per ADR-027 Next Action)
- **Related**: F007 (infra layer), F009 (API server), ADR-027 (decision record)

## Risk

| Risk | Mitigation |
|------|------------|
| `asyncpg` API differs from `psycopg2` — subtle behavior changes in type handling, NULL, JSONB | Comprehensive integration tests before merge; parallel-run period with feature flag |
| `pgvector` async support requires separate package (`pgvector-async`) or manual wire | Verify `pgvector` + `asyncpg` compatibility; test vector insert/select/cosine |
| Build-time path stays on `psycopg2` — two DB drivers in project | Acceptable; build is batch, runtime is serving; different access patterns justify different drivers |
| Call site rewrite is large (every `db.xxx` call) | Incremental: migrate hot path first (`search_by_nodes`, `get_node_ids_by_signatures`), then remaining methods |

## Open Questions

| # | Question | Status |
|---|----------|--------|
| OQ-1 | Feature flag: run both drivers in parallel during rollout, or hard cutover? | TBD (design gate) |
| OQ-2 | Keep `psycopg2` as sync fallback for non-async callers (debug.py)? | TBD (design gate) |
| OQ-3 | `pgvector` async: use `pgvector-async` package or manual SQL casting? | TBD (implementation) |

## Key Decisions

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| KD-1 | Split from F012 Phase B | asyncpg is larger scope, deserves own feature doc + ADR + review | 2026-07-01 |
| KD-2 | Build-time stays on psycopg2 | Batch inserts benefit from sync; no concurrency pressure at build time | 2026-07-01 |

## Links

| Type | Path | Description |
|------|------|-------------|
| **ADR** | `docs/decisions/ADR-027-db-concurrency-threadpool-now-asyncpg-later.md` | Origin: F012 KD-6 split |
| **Feature** | `docs/features/F012-runtime-robustness-hardening.md` | Predecessor: F012 Phase B (threadpool) |
| **Feature** | `docs/features/F007-infra-layer.md` | Infra layer being migrated |
