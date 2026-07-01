---
id: F012
name: Runtime Robustness Hardening
status: review
owner: agent
related_features: [F007, F007b, F008, F009, F011]
topics: [robustness, db, logging, retry, concurrency, validation, ops]
doc_kind: spec
created: 2026-07-01
updated: 2026-07-01
---

# F012: Runtime Robustness Hardening

> **Status**: review | **Owner**: agent | **Priority**: P0
>
> **Worktree:** `../ICBC-f012-phase-a` · **Branch:** `feat/f012-phase-a` · **Phase A:** 366 passed, 8 skipped · **Quality gate:** PASS

## Why

A critical review of the runtime path (`f007_infrastructure`, `f006_retrieval_engine`,
`f008_state_extraction`, `f009_api_server`, pipelines) found 27 robustness defects
spanning data-layer concurrency, silent error swallowing, missing retry, unbounded
compute, and ops blind spots. The single shared synchronous DB connection driven from
async FastAPI/SocketIO handlers is the top production outage risk. Several config keys
are dead (`llm.max_tokens`, `decision_tree.find_node_max_levels`), `retry.py` is unused,
and the whole codebase uses `print()` with no request correlation. Full findings + plan
live in `ROBUSTNESS_FIX_PLAN.md`.

## What

Six phases, sequenced by dependency. Detailed task/verify per item in
`ROBUSTNESS_FIX_PLAN.md`; this section is the phase-level summary.

### Phase A: Foundations

Structured logging (`f007_infrastructure/logging.py` + request-ID middleware), config
hardening (live-read ranking weights, typed `ConfigError`, placeholder-key guard), Python
tooling (widen `requires-python` to `>=3.11`, add ruff + mypy).

### Phase B: Data Layer

Connection pool (`ThreadedConnectionPool`) + async-safe access via threadpool, reconnect
on dropped socket. Wire `retry.py` into LLM/embedding/DB with a retryable-exception
whitelist; pass `max_tokens` + explicit timeout; chunk `embed_texts`. Typed
`LLMResponseError` for malformed JSON with logged fallback. Build-pipeline integrity:
loud failure on orphan node signature (no default to node 1), drop `str.replace`
serialization in favor of JSON, step timeout.

### Phase C: API Server

Input length limits + pydantic validation on SocketIO events, rate limiting. Session
store with TTL/eviction/cap + per-session locks. `/health` + `/readyz`, CORS, graceful
shutdown, degrade-mode boot (missing tree/taxonomy → 503 not crash).

### Phase D: Retrieval & State Correctness

Cap `_find_matching_nodes_subset` combinations (config-bounded). Bound
`descend_for_sentences` by `find_node_max_levels`, clamp confidence mid-loop. `merge_state`
dedup + hypothesis property tests. Relabel concurrency: lock CSV writes + global map
(interim), DB-backed relabel map (long-term, Phase F).

### Phase E: Freshness

NULL-embedding policy + backfill script. Taxonomy reload from DB. LRU cache on
`extract_state`.

### Phase F: Persistence & Migrations

Schema migration tool (alembic/yoyo) replacing `create_tables`. Sessions + relabel maps
to DB. Scheduler `last_run_at` persistence + midnight edge-case fix.

## Acceptance Criteria

### Phase A（Foundations）
- [x] AC-A1: `grep print(` in `src/` returns 0 outside CLI entrypoints; logs emit JSON with request_id
- [x] AC-A2: `RANKING_WEIGHTS`/`POOL_CAP` reflect `reload_config()` without process restart
- [x] AC-A3: Missing `---` fence raises typed `ConfigError` with path
- [x] AC-A4: Boot refuses `sk-placeholder` DEEPSEEK_API_KEY in non-dev env
- [x] AC-A5: `requires-python` widened to `>=3.11`; `ruff check src/` and `mypy src/` clean (or baseline allowlist)

### Phase B（Data Layer）
- [ ] AC-B1: N concurrent `/recommend` requests complete with no `InterfaceError`; killed PG → next request recovers within one retry
- [ ] AC-B2: `retry_call` wraps LLM/embedding; retries on 429/5xx/timeout, not on `ValueError`
- [ ] AC-B3: `llm.max_tokens` passed to API; `embed_texts` chunks by `embedding.batch_size` with per-batch retry
- [ ] AC-B4: Malformed LLM JSON → `LLMResponseError`, keyword fallback used, warning logged with truncated raw text
- [ ] AC-B5: Orphan node signature fails build loud (no default to node 1)
- [ ] AC-B6: `_write_py_results` round-trips a string value containing `": null"` unchanged

### Phase C（API Server）
- [ ] AC-C1: Oversize payload → 422; malformed SocketIO event → structured error; over-limit → 429
- [ ] AC-C2: 10k sessions created → memory bounded by cap + TTL eviction
- [ ] AC-C3: Concurrent same-session `customer_turn` → no lost transcript entries
- [ ] AC-C4: `/health` 200 liveness; `/readyz` 503 when tree/taxonomy missing; SIGTERM → pool closed, clean exit
- [ ] AC-C5: Boot with missing scored-tree → process stays up, `/recommend` 503

### Phase D（Retrieval & State）
- [ ] AC-D1: 20 facts + 20 emotions request → bounded time, `subset_search_truncated` fallback logged
- [ ] AC-D2: `descend_for_sentences` stops at `find_node_max_levels`; confidence never negative mid-loop
- [ ] AC-D3: `merge_state` hypothesis tests pass (idempotent, no dup, no loss, single-element branch_key)
- [ ] AC-D4: 50 concurrent `extract_state` → no corrupted CSV; map reads never see partial writes

### Phase E（Freshness）
- [ ] AC-E1: NULL-embedding rows logged at build; backfill script fills them
- [ ] AC-E2: DB keyword update → `/admin/reload-taxonomy` → new keyword matches without restart
- [ ] AC-E3: Repeated identical utterance → one LLM call (LRU cache hit)

### Phase F（Persistence & Migrations）
- [ ] AC-F1: Fresh DB → migrations apply; existing DB → idempotent no-op
- [ ] AC-F2: Restart mid-session → transcript recoverable from DB
- [ ] AC-F3: Restart across midnight → exactly one pipeline run per allowed day

## Dependencies

- **Evolved from**: F007/F007b/F009 (hardens the infra + API layers they built)
- **Blocked by**: none (F011 config externalization is complete and is a prerequisite enabler)
- **Related**: F008 (state extraction relabel concurrency), F006 (retrieval combinatorial path)

## Risk

| 风险 | 缓解 |
|------|------|
| DB pool migration changes connection semantics → regression in existing tests | Phase B lands behind feature flag; integration test with real PG (testcontainer) added before merge |
| `merge_state` refactor breaks downstream retrieval | Hypothesis property tests written first (TDD); existing retrieval tests must stay green |
| Migrations (Phase F) on a populated prod DB | Reversible migrations with down-paths; dry-run mode; tested on a clone first |
| Scope creep across 6 phases | Each phase is a separate PR; Phase F may split into its own feature doc if it grows |

## Open Questions

| # | 问题 | 状态 |
|---|------|------|
| OQ-1 | Async DB: threadpool on psycopg2 vs migrate hot path to asyncpg? | ✅ 已定 — threadpool now; asyncpg split into separate feature (see KD-6) |
| OQ-2 | Relabel map: interim file-lock vs go straight to DB-backed in Phase D? | ⬜ 未定 (defer to Phase D planning) |
| OQ-3 | Sessions persistence: DB now or defer to Phase F? | ⬜ 未定 (defer to Phase F planning) |
| OQ-4 | Phase ordering: land F (migrations) before B (pool)? | ✅ 已定 — keep A→B→…→F (foundations first) |
| OQ-5 | Phase B serialization vs ADR-008? | ✅ 已定 — keep `.py`, fix via `pprint.pformat` (KD-3) |
| OQ-6 | f008 LLM path live or legacy (ADR-009)? | ✅ 已定 — live; wire retry + LRU cache |

## Key Decisions

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| KD-1 | Six-phase plan, foundations first | Logging/config/tooling unblock all later phases | 2026-07-01 |
| KD-2 | Each phase = separate PR | Bounded review; rollback granularity | 2026-07-01 |
| KD-3 | Respect ADR-008: keep `.py` intermediate format, fix serialization via `pprint.pformat` (not JSON) | Memory-first rule; ADR-008 `accepted`; Human confirmed | 2026-07-01 |
| KD-4 | Phase D `merge_state` dedup via ordered-set semantics | LL-003 `accepted` (propagate-then-extend duplicates) | 2026-07-01 |
| KD-5 | Phase E extraction cache = simple LRU only | LL-002 `accepted` (over-engineered per-turn LLM extraction) | 2026-07-01 |
| KD-6 | Phase B uses threadpool on psycopg2 + ThreadedConnectionPool now; native asyncpg migration split into a separate feature (F013 candidate) | Human decision: asyncpg is larger scope, deserves its own feature doc + ADR | 2026-07-01 |

## Timeline

| 日期 | 事件 |
|------|------|
| 2026-07-01 | 立项 (kickoff) |
| 2026-07-01 | Design Gate approved (Human); KD-3..KD-6 recorded |
| 2026-07-01 | Phase A complete (A1–A8); AC-A1..A5 ✅ |

## Review Gate

## Files (Phase A)

### New
- `src/f007_infrastructure/logging.py` — structured logging (JsonFormatter, request_id contextvar)
- `src/tests/f007_infrastructure/test_logging.py`
- `src/tests/f007_infrastructure/test_no_print.py`
- `src/tests/f007_infrastructure/test_config_error.py`
- `src/tests/f007_infrastructure/test_pyproject.py`
- `src/tests/f009_api_server/test_request_id.py`
- `src/tests/f009_api_server/test_startup_guard.py`
- `src/tests/f006_retrieval_engine/test_live_config.py`
- `ruff.toml`, `mypy.ini`

### Modified
- `src/f009_api_server/server.py` — request-id middleware, placeholder guard, logger
- `src/f006_retrieval_engine/retrieval_ranking.py` — `get_ranking_weights()` live-read
- `src/f006_retrieval_engine/retrieval_engine.py` — `_pool_cap()` live-read
- `src/f007_infrastructure/config.py` — `ConfigError`, fence handling
- `src/f007_infrastructure/retry.py` + 8 library modules — `print`→`_log`
- `pyproject.toml` — `requires-python>=3.11`, ruff/mypy dev deps

## Implementation Plan

→ `docs/features/F012-implementation-plan.md` — Phase A in TDD step granularity (tasks A1–A8); Phases B–F outlined, each gets its own plan when its PR begins (KD-2).

## Review Gate

- Phase A: agent self-check (no behavior change expected)
- Phase B: Human review (DB concurrency is production-critical)
- Phase C: Human review (API contract changes)
- Phase D: agent self-check + hypothesis test evidence
- Phase E/F: Human review

## Links

| 类型 | 路径 | 说明 |
|------|------|------|
| **Plan** | `ROBUSTNESS_FIX_PLAN.md` | Full task/verify detail per issue (issues #1–#27) |
| **Plan** | `docs/features/F012-implementation-plan.md` | TDD step-level plan (Phase A full, B–F outlined) |
| **Feature** | `docs/features/F007-infra-layer.md` | Infra layer being hardened |
| **Feature** | `docs/features/F009-api-server.md` | API server being hardened |
| **Feature** | `docs/features/F011-config-externalization.md` | Config enabler (complete) |
| **ADR** | `docs/decisions/ADR-008-output-format-py-file.md` | Accepted: `.py` output format — governs Phase B serialization (KD-3) |
| **ADR** | `docs/decisions/ADR-009-eliminate-f002-llm-state-extraction.md` | Accepted: LLM state extraction eliminated — conflicts with current f008 code (OQ-6) |
| **ADR** | `docs/decisions/ADR-027-db-concurrency-threadpool-now-asyncpg-later.md` | Accepted: Phase B threadpool now, asyncpg → F013 (KD-6) |
| **Lesson** | `docs/lessons/LL-002-over-engineered-llm-extraction.md` | Accepted: governs Phase E cache simplicity (KD-5) |
| **Lesson** | `docs/lessons/LL-003-propagate-then-extend-duplicates.md` | Accepted: governs Phase D merge_state dedup (KD-4) |

## Review Notes (Phase A)

**Reviewer:** Human · **Date:** 2026-07-01 · **Verdict:** all 5 items fixed

| # | Feedback | Resolution | Commit |
|---|----------|------------|--------|
| 1 | Fix the ruff violations (no baseline) | Fixed all 186 violations (I001/F401/F541/UP015/E401/B007/B023/F841/B905/B006/UP031/E731/E701/B904/E402); removed baseline ignore; re-exports protected with `# noqa: F401` | `d49a481` |
| 2 | All should be checked by mypy | Full-repo mypy clean (75 files); fixed implicit Optional, None-globals, dict annotations, and a Token-reset bug in the request-id middleware | `bee3852` |
| 3 | Live read | Switched response-dict `RANKING_WEIGHTS` refs to `get_ranking_weights()` in server.py, retrieval_engine.py; removed unused import in debug.py | `1d1f193` |
| 4 | Do the follow-up | `git rm --cached` 33 tracked `.pyc` files (`.gitignore` already had `__pycache__/`+`*.pyc`) | `1d1f193` |
| 5 | Should use existing .env | Dropped `APP_ENV`; guard now fires on placeholder `DEEPSEEK_API_KEY` unconditionally (uses only existing `.env` key) | `1d1f193` |

**Post-fix verification:** 365 passed / 8 skipped · ruff clean (no baseline) · mypy clean (75 files) · 0 regressions.
