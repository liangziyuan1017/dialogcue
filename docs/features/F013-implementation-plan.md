# F013 Implementation Plan

## TDD Steps

### Phase 1: Async DB Core (db.py rewrite)

**Step 1.1 — Create `AsyncSentenceDB` class skeleton**
- TDD: Write test that `AsyncSentenceDB(dsn)` instantiates with `asyncpg` pool
- Implement: `class AsyncSentenceDB` with `asyncpg.create_pool(dsn)` in `__init__`
- Verify: test passes

**Step 1.2 — `async create_tables()`**
- TDD: Write test that `await db.create_tables()` creates all tables + indexes idempotently
- Implement: Port `create_tables()` SQL to async; `asyncpg` executes same DDL
- Verify: tables exist after call; second call is no-op

**Step 1.3 — `async upsert_nodes()`**
- TDD: Write test that `await db.upsert_nodes(nodes)` inserts and conflicts update
- Implement: `asyncpg` batch INSERT ON CONFLICT
- Verify: upsert semantics match psycopg2 version

**Step 1.4 — `async get_node_ids_by_signatures()`**
- TDD: Write test that returns `{path_signature: REMOVED_FIELD_id}` mapping
- Implement: `SELECT ... WHERE path_signature = ANY($1)` with asyncpg
- Verify: same REMOVED_FIELD_result shape

**Step 1.5 — `async search_by_nodes()`** (HOT PATH)
- TDD: Write test that returns sentences with `vec_score` computed in SQL
- Implement: pgvector cosine via `asyncpg`; handle `vector_cosine_ops` with manual SQL (no `pgvector.asyncpg` needed — `<=>` operator works at SQL level)
- Verify: vec_score matches psycopg2 version within floating point tolerance

**Step 1.6 — `async get_sentences_by_node()`**
- TDD: Write test that returns sentence metadata without embeddings
- Implement: async query by `node_id`
- Verify: same fields returned

**Step 1.7 — `async keyword_search()` and `async taxonomy_keyword_search()`**
- TDD: Write tests for FTS + trigram fallback
- Implement: Port both methods to async
- Verify: same ranking behavior

**Step 1.8 — `async search_similar()`**
- TDD: Write test with bitmask filter
- Implement: Port to async
- Verify: bitmask AND + vec_score

**Step 1.9 — `async upsert_sentences()`**
- TDD: Write test with pgvector embedding insert
- Implement: async INSERT ON CONFLICT with `np.array` → bytes for asyncpg vector
- Verify: embedding round-trips correctly

**Step 1.10 — `async close()`**
- TDD: Write test that pool closes gracefully
- Implement: `await self._pool.close()`
- Verify: no hanging connections

### Phase 2: Server Integration (server.py)

**Step 2.1 — Replace `run_in_threadpool(sync_db_call)` with `await async_db_call`**
- TDD: Write test that `/recommend` works end-to-end with async DB
- Implement: Replace `run_in_threadpool(recommend, ...)` — `recommend()` itself becomes async or wraps async DB calls
- Verify: same API response shape; no threadpool in DB path

**Step 2.2 — Lifespan: init async pool**
- TDD: Write test that app starts with `AsyncSentenceDB`
- Implement: `async with asyncpg.create_pool()` in lifespan; `app.state.db = AsyncSentenceDB(dsn)`
- Verify: pool created at startup, closed at shutdown

**Step 2.3 — SocketIO handlers**
- TDD: Write test that `customer_turn` event works with async DB
- Implement: Same `await` pattern as REST endpoint
- Verify: same behavior

### Phase 3: Debug.py Compatibility

**Step 3.1 — Wrap async DB calls for sync debug.py**
- TDD: Write test that `debug.py` still works
- Implement: `asyncio.run()` wrapper or keep `SentenceDB` (psycopg2) as sync fallback for debug
- Verify: debug UI functional

### Phase 4: Build-time Path (no change)

**Step 4.1 — Verify `build_tree_and_db.py` still works with psycopg2**
- No code change; just run and verify
- Build-time stays sync; `SentenceDB` (psycopg2) remains for batch operations

### Phase 5: Performance Validation

**Step 5.1 — Load test comparison**
- Run `wrk` or `locust` against both psycopg2+threadpool and asyncpg
- Measure p50/p95/p99 latency and max throughput
- Verify AC-5: p99 ≤ 80% of baseline

**Step 5.2 — Concurrent correctness**
- 50+ simultaneous `/recommend` requests
- Verify no `InterfaceError`, no thread exhaustion, correct results

## Checkpoint

After each step, run: `pytest src/tests/ -q` — all must pass before proceeding.
