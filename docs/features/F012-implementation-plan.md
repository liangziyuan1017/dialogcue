# F012 Runtime Robustness Hardening — Implementation Plan

**Feature:** F012 — `docs/features/F012-runtime-robustness-hardening.md`
**Goal:** Harden the runtime path (logging, config, DB concurrency, retry, validation, ops) against the 27 defects in `ROBUSTNESS_FIX_PLAN.md`.
**Acceptance Criteria:** See `docs/features/F012-runtime-robustness-hardening.md` (AC-A1..AC-F3).
**Architecture:** Six phases, foundations first. Phase A (this plan) = structured logging + config hardening + Python tooling. Each phase is a separate PR (KD-2). Phase B uses threadpool on psycopg2 now; asyncpg is deferred to F013 (ADR-027). Serialization stays `.py` via `pprint.pformat` (ADR-008, KD-3).
**Tech Stack:** Python ≥3.11, stdlib `logging`, pydantic v2, ruff, mypy, pytest.

> **Scope of this document:** Phase A in TDD step granularity. Phase B complete with review fixes. Phases C–F outlined; each gets its own plan doc when its PR begins (KD-2).
>
> **Merged:** Phase A + Phase B merged to `main` (2026-07-01). 392 passed / 8 skipped · ruff clean · mypy clean (81 files).

---

## Phase A — Foundations

### Task A1: Structured logging module

**Files:**
- Create: `src/f007_infrastructure/logging.py`
- Create: `src/tests/f007_infrastructure/test_logging.py`

**Step 1: Write failing test** — `test_get_logger_returns_logger_with_handler`, `test_json_formatter_emits_request_id`, `test_level_from_config`.
**Step 2: Run → fails** (module missing).
**Step 3: Implement** `get_logger(name)` returning a stdlib `logging.Logger`; `JsonFormatter` adding `request_id` from a contextvar; level read from `_cfg("logging.level", "INFO")`.
**Step 4: Run → passes.**
**Step 5: Commit** `feat(F012): A1 logging module`.

### Task A2: Request-ID middleware

**Files:**
- Modify: `src/f009_api_server/server.py`
- Create: `src/tests/f009_api_server/test_request_id.py`

**Step 1: Failing test** — POST `/recommend` → response header `X-Request-ID` present; log line for the request carries the same id.
**Step 2: Run → fails.**
**Step 3: Implement** FastAPI middleware generating `X-Request-ID` (or echoing inbound), binding into the contextvar from A1. Add a SocketIO connect handler that binds a per-sid request id.
**Step 4: Run → passes.**
**Step 5: Commit** `feat(F012): A2 request-id middleware`.

### Task A3: Replace `print` with logging

**Files:**
- Modify: every `src/**/*.py` with `print(` (except CLI `__main__` blocks in `whole_pipeline.py`, `build_tree_and_db.py`, `launch_ui.py` which route through logging but at INFO to stdout)
- Modify: `src/f007_infrastructure/retry.py:22` (the retry print)

**Step 1: Failing test** — `grep -rn "print(" src/ --exclude="*__main__*"` returns 0 (assertion test in `test_logging.py`).
**Step 2: Run → fails** (18+ prints remain).
**Step 3: Replace** each `print` with the module logger at the appropriate level (`warning` for fallbacks, `info` for progress, `error` for failures). Preserve message content.
**Step 4: Run → passes**; existing tests green.
**Step 5: Commit** `refactor(F012): A3 print→logging`.

### Task A4: Config live-read for ranking weights + pool cap

**Files:**
- Modify: `src/f006_retrieval_engine/retrieval_ranking.py:7-17` (remove module-level `RANKING_WEIGHTS` constant → function `_ranking_weights()` called at use site)
- Modify: `src/f006_retrieval_engine/retrieval_engine.py:12` (remove `POOL_CAP` constant → `_cfg("pool_cap", 50)` at call site)
- Modify: `src/f009_api_server/server.py` (update `RANKING_WEIGHTS` import → call)
- Modify: `src/tests/f006_retrieval_engine/test_retrieval_ranking.py`

**Step 1: Failing test** — `test_reload_config_changes_ranking_without_restart`: mutate config, call `reload_config()`, assert next `rank_sentences` call uses new weights.
**Step 2: Run → fails.**
**Step 3: Implement** live-read functions at call sites; remove import-time constants.
**Step 4: Run → passes**; full retrieval test suite green.
**Step 5: Commit** `refactor(F012): A4 live-read config`.

### Task A5: Typed `ConfigError` + fence handling

**Files:**
- Modify: `src/f007_infrastructure/config.py:89-95` (`_parse_frontmatter`)
- Modify: `src/tests/f007_infrastructure/test_config.py`

**Step 1: Failing test** — `test_missing_closing_fence_raises_config_error_with_path`.
**Step 2: Run → fails** (currently `ValueError` from `str.index`).
**Step 3: Implement** `class ConfigError(ValueError)`; catch `ValueError` in `_parse_frontmatter`, raise `ConfigError(path, msg)`.
**Step 4: Run → passes.**
**Step 5: Commit** `feat(F012): A5 ConfigError`.

### Task A6: Placeholder-key startup guard

**Files:**
- Modify: `src/f009_api_server/server.py` (lifespan startup)
- Modify: `src/f007_infrastructure/llm_client.py` (or a shared guard)
- Create: `src/tests/f009_api_server/test_startup_guard.py`

**Step 1: Failing test** — boot with `DEEPSEEK_API_KEY=sk-placeholder` and `APP_ENV=prod` → lifespan raises, `/readyz` reports DOWN. With `APP_ENV=dev` → boots.
**Step 2: Run → fails.**
**Step 3: Implement** guard in lifespan: if key startswith `sk-placeholder` and env != dev → set `app.state.ready=False` with reason (do not crash; let `/readyz` report).
**Step 4: Run → passes.**
**Step 5: Commit** `feat(F012): A6 placeholder-key guard`.

### Task A7: Widen `requires-python` + add ruff/mypy

**Files:**
- Modify: `pyproject.toml:9` (`>=3.14,<3.15` → `>=3.11`)
- Create: `ruff.toml`
- Create: `mypy.ini`
- Modify: `pyproject.toml` dev deps (add ruff, mypy)

**Step 1: Failing test** — `test_requires_python_allows_3_11` (parse pyproject, assert spec).
**Step 2: Run → fails.**
**Step 3: Implement** config changes; run `ruff check src/` and `mypy src/`; commit a baseline allowlist if non-empty.
**Step 4: Run → passes** (ruff/mypy clean or baseline-allowlisted).
**Step 5: Commit** `chore(F012): A7 python tooling`.

### Task A8: Phase A quality gate

**Step 1:** `pytest -q` → all green.
**Step 2:** `ruff check src/` clean.
**Step 3:** `mypy src/` clean (or baseline).
**Step 4:** Update feature doc: mark AC-A1..AC-A5 ✅, set `status: in-progress` (Phase A done, B–F pending), update `updated:` timestamp.
**Step 5: Commit** `docs(F012): Phase A complete`.

---

## Phase B — Data Layer (complete; AC-B1..B6 ✅)

- B1: `ThreadedConnectionPool` + `run_in_threadpool` offload + reconnect (AC-B1) ✅
- B2: Wire `retry_call` into LLM/embedding/DB with retryable whitelist (AC-B2) ✅
- B3: Pass `max_tokens`; chunk `embed_texts` by `embedding.batch_size` (AC-B3) ✅
- B4: `LLMResponseError` + logged keyword fallback (AC-B4) ✅
- B5: Orphan node signature loud failure (AC-B5) ✅
- B6: `_write_py_results` via `pprint.pformat` (ADR-008, KD-3) (AC-B6) ✅

**Review fixes:** double-putconn guard (LL-006), vector registration cache, zip strict=True, OperationalError test coverage. Post-fix: 392 passed / 8 skipped.

## Phase C — API Server (outlined)
- C1: Input limits + SocketIO pydantic events + rate limit (AC-C1)
- C2: `SessionStore` with TTL/eviction/cap + per-session locks (AC-C2, AC-C3)
- C3: `/health`, `/readyz`, CORS, graceful shutdown, degrade-mode boot (AC-C4, AC-C5)

## Phase D — Retrieval & State (outlined)
- D1: Combinatorial cap (AC-D1)
- D2: Bound `descend_for_sentences` by `find_node_max_levels` (AC-D2)
- D3: `merge_state` dedup + hypothesis tests (LL-003, KD-4) (AC-D3)
- D4: Relabel concurrency lock (interim) (AC-D4)

## Phase E — Freshness (outlined)
- E1: NULL-embedding policy + backfill (AC-E1)
- E2: Taxonomy reload from DB (AC-E2)
- E3: LRU cache on `extract_state` (LL-002, KD-5) (AC-E3)

## Phase F — Persistence & Migrations (outlined)
- F1: Migration tool (alembic/yoyo) (AC-F1)
- F2: Sessions + relabel maps to DB (AC-F2)
- F3: Scheduler `last_run_at` persistence + midnight fix (AC-F3)

---

## Straight-Line Check (Phase A)

| Step | Stays in final system? | Demo/test after | Cost if removed |
|---|---|---|---|
| A1 logging.py | ✅ | test_logging | No structured logs → A2/A3 blocked |
| A2 request-id | ✅ | test_request_id | No correlation across turns |
| A3 print→log | ✅ | grep test | Silent fallbacks stay silent |
| A4 live config | ✅ | reload test | Weights stale on reload (#27) |
| A5 ConfigError | ✅ | fence test | Cryptic ValueError on bad config |
| A6 placeholder guard | ✅ | boot test | Prod runs with dead key |
| A7 tooling | ✅ | ruff/mypy | No lint/type safety |

All on the A→B line. No spikes.
