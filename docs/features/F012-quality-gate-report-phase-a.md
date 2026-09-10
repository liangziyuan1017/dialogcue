# F012 Phase A — Quality Gate Report

**Spec:** `docs/features/F012-runtime-robustness-hardening.md`
**Plan:** `docs/features/F012-implementation-plan.md` (tasks A1–A8)
**原始需求:** `ROBUSTNESS_FIX_PLAN.md` (27 robustness defects)
**检查时间:** 2026-07-01 11:25
**Worktree:** `../ICBC-f012-phase-a` · **Branch:** `feat/f012-phase-a`

---

## Step 0 — 愿景覆盖

| # | 原始需求 (review issue) | AC 覆盖？ | 实现？ |
|---|--------------------------|-----------|--------|
| 1 | #6 no structured logging / broad except | AC-A1 | ✅ logging.py + print→_log in 9 modules |
| 2 | #27 config stale on reload | AC-A2 | ✅ get_ranking_weights() / _pool_cap() live-read |
| 3 | #11 config fence ValueError | AC-A3 | ✅ ConfigError with path |
| 4 | #26 placeholder key in prod | AC-A4 | ✅ startup guard, ready=False |
| 5 | #16 python 3.14 over-pin | AC-A5 | ✅ >=3.11, ruff + mypy introduced |

## Step 0.5 — 交付完整性

Phase A is **partial** (1 of 6 phases). Human explicitly agreed to phased PRs (KD-2, Design Gate). Phases B–F remain; each gets its own plan + PR. ✅ authorized partial delivery.

## Step 1–3 — 功能验收

| # | AC | 状态 | 代码位置 | 测试覆盖 |
|---|-----|------|----------|----------|
| 1 | AC-A1 no print in library + JSON logs w/ request_id | ✅ | `f007_infrastructure/logging.py`, 9 modules | `test_logging.py` (6), `test_no_print.py` (1) |
| 2 | AC-A2 weights reflect reload_config() | ✅ | `retrieval_ranking.py:17` `get_ranking_weights()`, `retrieval_engine.py:14` `_pool_cap()` | `test_live_config.py` (3) |
| 3 | AC-A3 missing fence → ConfigError w/ path | ✅ | `config.py:9` `ConfigError`, `config.py:95` | `test_config_error.py` (3) |
| 4 | AC-A4 placeholder key refused non-dev | ✅ | `server.py:60` `_check_api_key_guard` | `test_startup_guard.py` (3) |
| 5 | AC-A5 >=3.11 + ruff/mypy clean | ✅ | `pyproject.toml:9`, `ruff.toml`, `mypy.ini` | `test_pyproject.py` (2) |
| 6 | A2 request-REMOVED_FIELD_id middleware | ✅ | `server.py:80` `request_id_middleware` | `test_request_id.py` (3) |

## Step 4 — Runtime Guard

Not a production environment. Worktree `../ICBC-f012-phase-a`, branch `feat/f012-phase-a`. No live service probed. All evidence from worktree-local venv.

## Step 5 — Pen Check

No UI changes in Phase A. No `.pen` designs. ⚠️ N/A — skipped (no UI).

## Step 6–7 — 验证命令输出（本次真实运行）

```
pytest  → 366 passed, 8 skipped ✅  (baseline was 345 passed, 8 skipped → +21 new tests, 0 regressions)
ruff check src/ → All checks passed! ✅
mypy (new modules logging.py, config.py) → Success: no issues found in 2 source files ✅
AC-A1 grep guard → 1 passed ✅
```

## Step 7.5 — Artifact Hygiene

- Root media (`*.png/*.jpg/*.mp4/*.gif`): **none** ✅
- ⚠️ **CAUTION (pre-existing):** 33 `*.pyc` files are tracked in the repo (under `modules/agent-memory/`). Two changed in this diff (`f009_api_server/__pycache__/*.pyc`) because `server.py` was edited. These are **not introduced by Phase A** — pre-existing tracked build artifacts. Recommend a follow-up to `git rm --cached` them and add `__pycache__/` to `.gitignore`. Out of scope for this gate.

## Step 8 — 合规结论

| Gate | Result |
|------|--------|
| Vision coverage | ✅ 5/5 Phase A issues addressed |
| AC compliance | ✅ 5/5 AC-A items + request-REMOVED_FIELD_id middleware |
| Tests | ✅ 366 passed, 0 regressions |
| Lint (ruff) | ✅ clean (baseline allowlist documented) |
| Type (mypy) | ✅ clean on new modules |
| Artifact hygiene | ⚠️ pre-existing pyc (not Phase A) |
| Doc sync | ✅ feature doc updated (AC ✅, Files table, timeline) |

**Verdict: PASS** — Phase A is ready for `request-review`.

### Caveats for reviewer
1. Ruff runs with a **baseline ignore list** (I001/F401/F541/UP015/E401 + B-rules) covering 123 pre-existing violations. Tightening is deferred to a future cleanup PR; new code is held to the full rule set where applicable.
2. Mypy is scoped to new modules (`logging.py`, `config.py`); full-repo mypy is deferred (most modules lack type hints — would require a broad typing effort).
3. `print` remains in 5 CLI entrypoints (`whole_pipeline.py`, `build_tree_and_db.py`, `launch_ui.py`, `check_data_format.py`, `serve_tree.py`) by design (AC-A1 exclusion).
4. `RANKING_WEIGHTS` module-level constant kept as a backward-compat snapshot; live read via `get_ranking_weights()` at the hot path. `server.py`/`debug.py` response dicts still reference the snapshot — Phase B/C can switch them to live read.

---

## Update Log

**2026-07-10 — `ROBUSTNESS_FIX_PLAN.md` moved:** The `原始需求` reference above points to `ROBUSTNESS_FIX_PLAN.md` at project root. The file has been moved to `old_files/ROBUSTNESS_FIX_PLAN.md`. The 27 defects are summarized in `F012-runtime-robustness-hardening.md`.
