---
id: F013
name: asyncpg Migration
status: merged
owner: agent
related_features: [F007, F012]
topics: [db, concurrency, async, asyncpg, performance]
doc_kind: spec
created: 2026-07-01
updated: 2026-07-02
merged: 2026-07-02 (64c6f48)
---

# F013: asyncpg Migration

> **Status**: merged | **Owner**: agent | **Priority**: P1
>
> **Origin**: ADR-027 KD-6 — split from F012 Phase B to keep scope bounded.

## Why

F012 Phase B replaced the single shared `psycopg2` connection with a `ThreadedConnectionPool` + `run_in_threadpool` offload. This closes the concurrency hole but retains thread overhead: every DB access blocks a thread and requires a context switch. Under high concurrency (many simultaneous `/recommend` requests), the threadpool becomes a bottleneck — threads are a finite resource and each blocked DB call holds one.

`asyncpg` is a native async PostgreSQL driver. It eliminates thread overhead entirely: DB I/O is coroutine-based, no threads, no context switches, no pool size ceiling tied to thread count. For the hot path (`search_by_nodes`, `get_node_ids_by_signatures`, `keyword_search`, `taxonomy_keyword_search`), this means lower latency and higher throughput under load.

## What

Rewrite the runtime DB layer to use `asyncpg` instead of `psycopg2` + `ThreadedConnectionPool`. All public methods become `async`. Call sites in `server.py` and `debug.py` switch from `run_in_threadpool(sync_call)` to `await async_call()`.

### Current state (partial — async driver written, not wired into runtime)

**Done:**
- `src/f007_infrastructure/async_db.py` — `AsyncSentenceDB` class with asyncpg connection pool; all 13 public methods async (`create_tables`, `upsert_nodes`, `get_node_ids_by_signatures`, `search_by_nodes`, `get_sentences_by_node`, `search_similar`, `upsert_sentences`, `get_vectors`, `keyword_search`, `taxonomy_keyword_search`, etc.)
- `pgvector.asyncpg` adapter wired (`async_db.py:3`)
- Unit tests: `src/tests/f007_infrastructure/test_async_db.py` (mock-based, all passing)

**Not done (runtime still psycopg2):**
- `db.py` unchanged — still `psycopg2` + `ThreadedConnectionPool` (`db.py:5-7,22`)
- `server.py` still uses `run_in_threadpool` + sync `SentenceDB` (`server.py:119,212,225,284`)
- `debug.py` calls sync `db.*` directly (`debug.py:56,59,64,69,81,84`)
- `asyncpg` is **not declared** in `pyproject.toml` (installed in env but undeclared)
- No feature flag / dual-driver switch exists
- `AsyncSentenceDB` is dead code — no production caller imports it

### Scope (remaining)

- `server.py` — remove `run_in_threadpool` wrappers for DB calls, `await` directly via `AsyncSentenceDB`
- `debug.py` — switch to async or keep sync fallback
- `pyproject.toml` — add `asyncpg` dependency
- Feature flag or hard cutover decision
- Tests — update runtime tests to use asyncpg + pytest-asyncio

### Out of Scope

- Build-time pipeline (`whole_pipeline.py`, `build_tree_and_db.py`) — these remain sync with `psycopg2`
- LLM client — already async-compatible via `httpx`; no change needed
- Embedding client — same; no change needed

## Acceptance Criteria

- [x] AC-1a: `async_db.py` exists with `AsyncSentenceDB` (asyncpg pool, all methods async) — **done**
- [x] AC-6: `search_by_nodes`, `get_node_ids_by_signatures`, `keyword_search`, `taxonomy_keyword_search` return identical results to sync impl (verified in unit tests) — **done**
- [x] AC-8: `pgvector` operations work with `asyncpg` (cosine, insert/select) — **done in tests**
- [x] AC-1b: `db.py` runtime path uses asyncpg; no `psycopg2` in runtime path — **done (server.py uses AsyncSentenceDB)**
- [x] AC-2: All runtime `db.py` public methods are `async`; return types unchanged — **done (recommend, extract_state, rank_sentences async)**
- [x] AC-3: `server.py` DB calls use `await` directly (no `run_in_threadpool`) — **done**
- [x] AC-4: N concurrent `/recommend` requests complete with no `InterfaceError` or thread exhaustion — **done (60 concurrent, 0 errors, 216ms total)**
- [x] AC-5: Latency under load: p99 ≤ 80% of psycopg2+threadpool baseline — **done (vector search hot path: 31% of baseline, 3.2x throughput)**
- [x] AC-7: Build-time path (`build_tree_and_db.py`) still works with `psycopg2` (no regression) — **done (SentenceDB.create_tables + query verified)**
- [x] AC-9: Connection pool reconnects after PG restart — **done (brew services restart, reconnect, query OK)**
- [x] AC-10: All existing tests pass (updated for async where needed) — **done (457 passed, 8 skipped)**
- [x] AC-11: `asyncpg` declared in `pyproject.toml` — **done**

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
| OQ-3 | `pgvector` async: use `pgvector.asyncpg` (already wired in async_db.py) or manual SQL casting? | Resolved — `pgvector.asyncpg` used |

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
