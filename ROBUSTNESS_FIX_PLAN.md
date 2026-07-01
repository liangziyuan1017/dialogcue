# Robustness Fix Plan

Derived from the critical review. Issues referenced as `#N` map to the review's
numbered findings. No implementation here — this is the execution plan.

Priority order is also the recommended execution order: later phases depend on
infrastructure introduced earlier (logging, config, DB layer). Each task lists
**touch** (files/modules), **what**, and **verify** (acceptance criteria).

---

## Phase 0 — Foundations (do first; everything else builds on these)

### 0.1 Structured logging
- **Touch:** new `src/f007_infrastructure/logging.py`; replace `print` across `src/`.
- **What:**
  - Single `get_logger(name)` returning a configured stdlib `logging` logger
    (JSON formatter in prod, human-readable in dev) with level from
    `config.md` (`logging.level`, default `INFO`).
  - Request-ID middleware in `server.py` (FastAPI + SocketIO) — generate/propagate
    `X-Request-ID`; bind into log context for every turn.
  - Replace every `print(` in `src/` with the appropriate logger call. Keep
    CLI scripts (`whole_pipeline.py`, `build_tree_and_db.py`) on stdout but
    routed through logging so level/destination is configurable.
- **Verify:** grep `print(` in `src/` returns 0 outside CLI entrypoints; logs
  emit JSON with request_id in a test run.

### 0.2 Config hardening
- **Touch:** `src/f007_infrastructure/config.py`, `config.md`.
- **What:**
  - Make `RANKING_WEIGHTS` and `POOL_CAP` read live via `get(...)` at call
    sites instead of import-time constants (remove `#27` stale-on-reload).
  - Catch `ValueError` in `_parse_frontmatter` when no closing `---`; raise a
    typed `ConfigError` with path + message (`#11`).
  - Add `logging.level` and `server.request_max_chars` to `config.md` + validation rules.
  - Add a startup guard: if `DEEPSEEK_API_KEY` startswith `sk-placeholder` and
    env != dev → refuse to boot (`#26`).
- **Verify:** `test_config.py` covers missing fence, placeholder key, and
  live-reload of ranking weights without process restart.

### 0.3 Python tooling
- **Touch:** `pyproject.toml`, new `ruff.toml`/`mypy.ini`.
- **What:**
  - Widen `requires-python` to `>=3.11` (no 3.14 features used) (`#16`).
  - Add `ruff` (E/F/I/UP/B) + `mypy --strict` (allow gradual opt-out via
    `# type: ignore` with reason) configs; wire into `[project.optional-dependencies] dev`.
- **Verify:** `ruff check src/` and `mypy src/` run clean (or with an explicit
  baseline allowlist committed).

---

## Phase 1 — Data layer (highest production risk)

### 1.1 Connection pool + async-safe access
- **Touch:** `src/f007_infrastructure/db.py`, `src/f009_api_server/server.py`.
- **What (`#1`, `#2`):**
  - Replace single `psycopg2.connect` with `psycopg2.pool.ThreadedConnectionPool`
    (min 1, max from `config.md` `db.pool_max`).
  - Introduce a context manager `db.connection()` that checks out a conn,
    runs `SELECT 1` ping on checkout (cheap; or use `conn.closed` check), and
    returns it; on `OperationalError` reconnect once.
  - Move `register_vector` to per-connection lazy init (already partially there).
  - In FastAPI handlers, run DB work in `await run_in_threadpool(...)` so the
    sync driver doesn't block the event loop; or migrate hot path to `asyncpg`
    (decision point — prefer threadpool first to limit scope).
  - Close pool in `lifespan` shutdown.
- **Verify:** `test_db_integration.py` runs N concurrent recommend requests
  with no `InterfaceError`/serialization; kill PG mid-test → next request
  recovers within one retry.

### 1.2 Retry wiring
- **Touch:** `llm_client.py`, `embeddings.py`, `db.py` (transient errors only).
- **What (`#7`, `#8`, `#2`):**
  - Wrap `call_deepseek` / `embed_texts` in `retry_call` with a whitelist of
    retryable exceptions (network/timeout/429/5xx), not `Exception`.
  - Pass `max_tokens=_cfg("llm.max_tokens")` and an explicit `timeout` to the
    OpenAI client (`#7` dead config).
  - Chunk `embed_texts` into batches of `config.md` `embedding.batch_size`
    (new key) with per-batch retry; partial-failure policy: retry batch, then
    zero-fill missing rows and log a warning (`#8`).
  - DB: retry transient `OperationalError` on read queries only (never on
    writes inside a transaction).
- **Verify:** unit tests inject a flaky client asserting retry happens on 429
  but not on `ValueError`; `embed_texts` of 1000 texts returns 1000 vecs even
  if one batch fails (with a logged warning).

### 1.3 Malformed LLM JSON handling
- **Touch:** `llm_client.py`, `state_extraction.py`.
- **What (`#7`):**
  - `call_deepseek_json` catches `json.JSONDecodeError` → raise a typed
    `LLMResponseError` carrying raw text.
  - `extract_state_llm` lets it propagate; `extract_state` already falls back
    to keyword — but log the failure with request_id and raw text (truncated).
  - Add a strict-mode flag for pipeline offline runs (raise instead of fallback).
- **Verify:** test with a stubbed LLM returning prose → keyword fallback used,
  warning logged with raw text.

### 1.4 Build pipeline integrity
- **Touch:** `build_tree_and_db.py`, `whole_pipeline.py`.
- **What (`#3`, `#5`):**
  - `build_tree_and_db.py:119`: if `node_sig` not in map → log error and skip
    the sentence (or fail the build with a count), never default to `1`.
  - `_write_py_results`: stop doing `str.replace` on serialized JSON. Write a
    real Python literal via `pprint.pformat(results, width=120)` or switch
    intermediate files to `.json` + `json.dump` (update `_load_py_results`
    accordingly). Prefer `.json` to drop the custom format entirely.
  - Add `subprocess.run(..., timeout=_cfg("pipeline.step_timeout"))` to
    `_run_llm_step`; on `TimeoutExpired` → retry per `1.2`, then fail.
- **Verify:** build with a deliberately orphaned signature fails loud;
  round-trip of `_write_py_results` preserves a string value `"x: null y"`.

---

## Phase 2 — API server robustness

### 2.1 Input validation & limits
- **Touch:** `server.py`, `config.md`.
- **What (`#14`):**
  - Add `max_length` to `RecommendRequest` fields
    (`customer_utterance`, `conversation_context`) from
    `server.request_max_chars`; 422 on overflow.
  - Validate SocketIO event payloads with pydantic models
    (`StartSessionIn`, `CustomerTurnIn`, `CollectorTurnIn`) — reject with a
    structured error instead of silent `data.get`.
  - Add a global rate limiter (per-IP token bucket) on `/recommend` and
    SocketIO `customer_turn` — `config.md` `server.rate_limit_rps`.
- **Verify:** tests for oversize payload → 422; malformed socket event →
  structured error; rate-limit → 429.

### 2.2 Session store
- **Touch:** `server.py`, new `src/f009_api_server/session_store.py`.
- **What (`#9`):**
  - Extract `sessions` into `SessionStore` with: max sessions cap, TTL
    (`server.session_ttl`), periodic eviction task, lock per session id
    (`asyncio.Lock`) for same-session mutation.
  - Optional: persist transcript to DB on `end_session` and on TTL eviction
    (so restarts don't lose in-flight transcripts). At minimum, log eviction.
- **Verify:** load test creating 10k sessions → capped/evicted, memory bounded;
  concurrent `customer_turn` for same session → no lost transcript entries.

### 2.3 Health, CORS, graceful shutdown
- **Touch:** `server.py`, `config.md`.
- **What (`#15`):**
  - `/health` (liveness: process up) and `/readyz` (readiness: DB ping +
    scored-tree loaded + taxonomy loaded).
  - CORS middleware configurable via `server.allowed_origins`.
  - `lifespan` shutdown: close DB pool, flush logs, stop eviction task.
  - Degrade-mode boot: if scored-tree/taxonomy missing, log error, serve
    `/health=DOWN` and 503 on `/recommend` instead of crashing (`#10`).
- **Verify:** boot with missing tree → `/readyz` 503, process stays up;
  SIGTERM → pool closed, clean exit.

### 2.4 Startup file loads
- **Touch:** `server.py`.
- **What (`#10`):**
  - Wrap `_load_scored_tree` / `_init_taxonomy` in try/except → on failure set
    `app.state.ready = False` and record the error; `/readyz` reports it.
- **Verify:** covered by 2.3 tests.

---

## Phase 3 — Retrieval & state correctness

### 3.1 Combinatorial cap
- **Touch:** `retrieval_engine.py`, `config.md`.
- **What (`#13`):**
  - Add `decision_tree.max_subset_combinations` (default 4096); accumulate a
    counter across the drop-level loops and break early once exceeded, logging
    a `subset_search_truncated` fallback.
  - Also cap input label count at the API layer (reject > `max_labels`).
- **Verify:** test with 20 facts + 20 emotions → bounded time, fallback flagged.

### 3.2 Bounded descend
- **Touch:** `retrieval_engine.py`.
- **What (`#12`):**
  - Use `_cfg("decision_tree.find_node_max_levels")` as the loop bound in
    `descend_for_sentences`; clamp confidence to `>= 0` inside the loop.
- **Verify:** deep-tree test stops at max_levels; confidence never negative
  mid-loop.

### 3.3 merge_state correctness
- **Touch:** `state_extraction.py`, `src/tests/f008_state_extraction/`.
- **What (`#17`):**
  - Dedup `inherited_facts`/`inherited_emotions` via ordered-set semantics.
  - Add property-based tests (hypothesis) for `merge_state`:
    idempotency under repeated identical extraction, no duplicates, no loss of
    prior inherited labels, branch_key always single-element.
  - Document the intended branch_key semantics in a docstring before writing tests.
- **Verify:** hypothesis tests pass on 1000 cases; existing retrieval tests green.

### 3.4 Relabel concurrency
- **Touch:** `state_extraction.py`.
- **What (`#4`):**
  - Guard `_append_relabel_to_csv` and the global map updates with a module-level
    `threading.Lock` (DB-offloaded path is Phase 5; this is the interim fix).
  - Better: write new mappings to the DB (`taxonomy_keywords`-style table) and
    load the map from DB at startup + cache-invalidate on write. Mark the CSV
    as legacy.
- **Verify:** 50 concurrent `extract_state` calls → no corrupted CSV (line count
  == unique mappings); map reads never see partial writes.

---

## Phase 4 — Embedding & taxonomy freshness

### 4.1 Embedding NULL policy
- **Touch:** `db.py`, `build_tree_and_db.py`.
- **What (`#23`):**
  - Decide explicitly: either `embedding` becomes `NOT NULL` with a zero-vector
    default, or `search_similar` logs the count of NULL-embedding rows skipped.
  - Add a backfill script (`scripts/backfill_missing_embeddings.py`) that finds
    NULL embeddings and embeds them.
- **Verify:** build with one unembeddable sentence → logged, backfill fills it.

### 4.2 Taxonomy reload
- **Touch:** `server.py`.
- **What (`#19`):**
  - Load taxonomy from DB (join `taxonomy_keywords`) instead of the JSON file
    at startup; add a `/admin/reload-taxonomy` endpoint (auth-gated) and/or a
    file-watcher. Keep JSON as a fallback.
- **Verify:** update a keyword in DB → reload → new keyword matches without restart.

### 4.3 State extraction caching
- **Touch:** `state_extraction.py`, `config.md`.
- **What (`#20`):**
  - Add an LRU cache on `extract_state` keyed by
    `hash(utterance + taxonomy_version)` with `extraction.cache_size`.
  - Invalidate on taxonomy reload.
- **Verify:** repeated identical utterance → one LLM call (counted via stub).

---

## Phase 5 — Persistence & migrations (larger; schedule deliberately)

### 5.1 Schema migrations
- **Touch:** new `src/f007_infrastructure/migrations/` (e.g. yoyo or alembic).
- **What (`#22`):**
  - Introduce a migration tool; convert `create_tables` into the baseline
    migration. Each future schema change is a versioned migration.
  - `SentenceDB.create_tables` becomes a thin "ensure migrations applied" call.
- **Verify:** fresh DB → migrations apply; existing DB → no-op idempotent.

### 5.2 Sessions & relabel maps to DB
- **Touch:** `session_store.py`, `state_extraction.py`, migrations.
- **What (`#9`, `#4` long-term):**
  - Persist sessions/transcripts to DB (table `sessions`, `transcript_turns`).
  - Move relabel map to DB table `relabel_map(category, tag, new_label)`; drop CSV writes.
- **Verify:** restart mid-session → transcript recoverable; relabel map survives restart.

---

## Phase 6 — Tests, CI, observability

### 6.1 Test gaps
- **Touch:** `src/tests/`.
- **What (`#24`):**
  - Integration test: real PG (testcontainer) + stubbed LLM → full `/recommend`
    round trip asserting DB-backed ranking.
  - Scheduler tests (forbidden-window crossing, midnight boundary, `ran_today` reset).
  - Config validation error tests (bad sums, out-of-range, missing fence).
  - Concurrent sessions test (Phase 2.2).
  - Large-state combinatorial cap test (Phase 3.1).
  - Malformed-LLM-JSON test (Phase 1.3).
- **Verify:** `pytest -q` green; coverage report committed as a check artifact.

### 6.2 CI
- **Touch:** `.github/workflows/`.
- **What (`#25`):**
  - Workflow: ruff + mypy + pytest on every PR; a smoke job that boots the
    server with a stubbed DB/LLM and hits `/readyz`.
  - Require green checks for merge (branch protection).
- **Verify:** PR opens → checks run; failing check blocks merge.

### 6.3 Scheduler persistence
- **Touch:** `whole_pipeline.py`.
- **What (`#22` scheduler part):**
  - Persist `last_run_at` to a small state file (or DB) so a restart doesn't
    double-run or skip; fix the midnight `ran_today` reset edge cases with
    explicit date comparison instead of boolean.
- **Verify:** restart across midnight → exactly one run per allowed day.

---

## Sequencing summary

```
Phase 0  ──→  Phase 1  ──→  Phase 2  ──→  Phase 3
(foundations)   (data)       (API)        (retrieval)
                                              │
                                              ▼
Phase 4  ──→  Phase 5  ──→  Phase 6
(freshness)   (persistence) (tests/CI)
```

Phases 0–1 should land first and be reviewable as one PR each. Phases 2–3 can
proceed in parallel once 1.1 is merged. Phase 5 is the largest and may be
deferred behind a feature doc if scope grows.

## Out of scope for this plan
- Algorithmic changes to ranking weights / scoring formulas (config-only tuning).
- UI work in `f010_api_mock_ui`.
- The agent-routing/module scaffolding under `modules/`, `registry/`, etc.
