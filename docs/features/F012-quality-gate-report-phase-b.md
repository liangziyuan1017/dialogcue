# F012 Phase B — Quality Gate Report

**Spec:** `docs/features/F012-runtime-robustness-hardening.md`
**Plan:** `ROBUSTNESS_FIX_PLAN.md` (Phase 1 — Data layer)
**检查时间:** 2026-07-01 14:55
**Worktree:** `../ICBC-f012-phase-b` · **Branch:** `feat/f012-phase-b`

---

## Step 0 — 愿景覆盖

| # | 原始需求 (review issue) | AC 覆盖？ | 实现？ |
|---|--------------------------|-----------|--------|
| 1 | #1/#2 single sync DB connection | AC-B1 | ✅ ThreadedConnectionPool + connection() ctx manager |
| 2 | #7/#8 retry + max_tokens + chunking | AC-B2, AC-B3 | ✅ retry_call whitelist, max_tokens+timeout, batch chunking |
| 3 | #7 malformed LLM JSON | AC-B4 | ✅ LLMResponseError + logged keyword fallback |
| 4 | #3 orphan node signature | AC-B5 | ✅ loud ValueError, no default to node 1 |
| 5 | #5 str.replace serialization | AC-B6 | ✅ pprint.pformat (ADR-008, KD-3) |

## Step 0.5 — 交付完整性

Phase B is complete (all 6 tasks B1–B6). All AC-B items checked. Phases C–F remain.

## Step 1–3 — 功能验收

| # | AC | 状态 | 代码位置 | 测试覆盖 |
|---|-----|------|----------|----------|
| 1 | AC-B1 pool + reconnect | ✅ | `db.py` ThreadedConnectionPool, `connection()` | `test_db_pool.py` (6) |
| 2 | AC-B2 retry whitelist | ✅ | `retry.py` retryable param, `llm_client.py` RETRYABLE_LLM_ERRORS | `test_retry_whitelist.py` (5) |
| 3 | AC-B3 max_tokens + chunking | ✅ | `llm_client.py:31` max_tokens+timeout, `embeddings.py:34` batch chunking | `test_llm_retry_chunking.py` (4) |
| 4 | AC-B4 LLMResponseError | ✅ | `llm_client.py:22` LLMResponseError, `state_extraction.py:242` catch+log | `test_llm_response_error.py` (4) |
| 5 | AC-B5 orphan loud failure | ✅ | `build_tree_and_db.py:120` orphan_sigs collection + raise | `test_orphan_node.py` (2) |
| 6 | AC-B6 pprint.pformat | ✅ | `whole_pipeline.py:59`, `build_and_score_tree.py:24` | `test_write_py_results.py` (4) |

## Step 4 — Runtime Guard

Not a production environment. Worktree `../ICBC-f012-phase-b`, branch `feat/f012-phase-b`. No live PG probed. Pool behavior verified via mock-based tests.

## Step 5 — Pen Check

No UI changes in Phase B. ⚠️ N/A — skipped (no UI).

## Step 6–7 — 验证命令输出（本次真实运行）

```
pytest  → 392 passed, 8 skipped ✅  (Phase A was 366 → +26 new tests, 0 regressions)
ruff check src/ → All checks passed! ✅
mypy src/ → Success: no issues found in 81 source files ✅
```

## Step 7.5 — Artifact Hygiene

- Root media: **none** ✅
- Tracked `.pyc`: **0** ✅

## Step 8 — 合规结论

| Gate | Result |
|------|--------|
| Vision coverage | ✅ 5/5 Phase B issues addressed |
| AC compliance | ✅ 6/6 AC-B items |
| Tests | ✅ 392 passed, 0 regressions |
| Lint (ruff) | ✅ clean |
| Type (mypy) | ✅ clean (81 source files) |
| Artifact hygiene | ✅ |
| Doc sync | ✅ feature doc updated (AC ✅, Files table, timeline) |

**Verdict: PASS** — Phase B is ready for `request-review`.

### Caveats for reviewer
1. AC-B1 "killed PG → next request recovers" is verified structurally (closed-connection replacement in `connection()` ctx manager); a real-PG integration test (testcontainer) is deferred to Phase 6 (test gaps).
2. `run_in_threadpool` was applied to `extract_state` in `/recommend`; `recommend` itself ran sync in the event loop. **F013 (merged) superseded this**: `recommend` and `extract_state` are now async via `asyncpg`; `run_in_threadpool` removed from runtime.
3. `RETRYABLE_LLM_ERRORS` covers `APITimeoutError`, `APIConnectionError`, `RateLimitError`, `InternalServerError`. `BadRequestError`/`AuthenticationError` are not retried (permanent).
4. `embed_texts` zero-fills failed batches after exhausting retries; partial-failure policy is "retry batch, then zero-fill + warn" (not "fail entire call").

---

## Update Log

**2026-07-10 — `ROBUSTNESS_FIX_PLAN.md` moved:** The `Plan` reference above points to `ROBUSTNESS_FIX_PLAN.md` at project root. The file has been moved to `old_files/ROBUSTNESS_FIX_PLAN.md`.
