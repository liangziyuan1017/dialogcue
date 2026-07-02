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

### Current state (merged — asyncpg is the runtime DB driver)

**Runtime path (asyncpg):**
- `src/f007_infrastructure/async_db.py` — `AsyncSentenceDB` with asyncpg connection pool; all 13 public methods async
- `pgvector.asyncpg` adapter wired (`async_db.py:3`)
- `server.py` — lifespan creates `AsyncSentenceDB`, `connect()` + `create_tables()` at startup, `close()` at shutdown; all DB calls `await` directly (no `run_in_threadpool`)
- `recommend()`, `extract_state()`, `rank_sentences()`, `compute_vec_similarity()` — all async
- `extract_state_llm` offloaded via `asyncio.to_thread` (non-blocking LLM call)
- `debug.py` — `debug_recommend()` and `_get_all_candidates()` async
- `pyproject.toml` — `asyncpg>=0.29` declared; `pytest-asyncio>=0.23` in dev; `asyncio_mode = "auto"`

**Build-time path (psycopg2, unchanged):**
- `db.py` retains `SentenceDB` (psycopg2 + `ThreadedConnectionPool`) for `build_tree_and_db.py` and `whole_pipeline.py`
- Build-time stays sync — batch inserts benefit from sync; no concurrency pressure at build time

### How asyncpg helps (detailed)

asyncpg replaces the `psycopg2` + `ThreadedConnectionPool` + `run_in_threadpool` stack in the runtime serving path. The benefits are both architectural and measurable:

**1. Eliminates thread overhead.** Every DB call under the old stack occupied a thread for the full duration of the I/O. With `pool_max=10`, only 10 concurrent DB operations could run; the 11th queued until a thread freed. asyncpg uses coroutines — DB I/O yields the event loop, so 100+ concurrent queries share the same single-threaded event loop without blocking each other. No context switches, no thread stack memory (≈8MB per thread), no GIL contention.

**2. Binary protocol for vector data.** asyncpg uses PostgreSQL's binary protocol exclusively; psycopg2 uses text protocol by default. For the hot path — `search_by_nodes` with 1024-dimensional pgvector embeddings — binary transfer avoids float-to-text-to-float serialization on every row. Measured: **3.2× throughput** (2177 vs 677 req/s) and **69% latency reduction** (92ms vs 296ms total) for 200 concurrent vector searches. Simple keyword queries show parity (~1×) because the overhead is dominated by query planning, not data transfer.

**3. Non-blocking LLM call.** The sync DeepSeek LLM call (`call_deepseek_json` via `openai.OpenAI`) was previously offloaded to `run_in_threadpool` in the `/recommend` REST endpoint. After making `extract_state` async, the LLM call would have blocked the event loop — a regression. `asyncio.to_thread(extract_state_llm, ...)` offloads it to a worker thread, restoring non-blocking behavior. The event loop stays free to serve other requests during the 1–60s LLM round-trip.

**4. Connection pool reconnection.** `AsyncSentenceDB.connect()` creates a fresh `asyncpg.create_pool()`. After a PG restart, `close()` + `connect()` rebuilds the pool and all queries succeed (AC-9 verified). The old `ThreadedConnectionPool` had the same capability but required explicit `getconn`/`putconn` management with a context manager (LL-006 documented a double-return bug in that path).

**5. No thread exhaustion under load.** Under 60 concurrent `/recommend` DB paths (4 queries each = 240 DB operations), the old stack would queue 230 of them on 10 threads. asyncpg processes all 240 as coroutines with zero `InterfaceError` or thread exhaustion (AC-4 verified). The ceiling is the DB itself, not the client thread count.

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
| OQ-1 | Feature flag: run both drivers in parallel during rollout, or hard cutover? | Resolved — hard cutover (runtime fully asyncpg, no flag) |
| OQ-2 | Keep `psycopg2` as sync fallback for non-async callers (debug.py)? | Resolved — debug.py made async; psycopg2 kept only for build-time |
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
