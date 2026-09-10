---
REMOVED_FIELD_id: LL-005
title: "Ruff F401 auto-fix breaks re-exports; ContextVar middleware must use reset(token) not set(token)"
doc_kind: lesson
feature_ids: [F012]
topics: [lint, ruff, typing, mypy, middleware, contextvars]
status: accepted
created: 2026-07-01
schema_version: 1
knowledge:
  authority: validated
  activation: scoped
  status: active
  exportability: project_only
  source_ids: [F012]
  review_cycle_days: 90
---

# LL-005: Ruff F401 auto-fix breaks re-exports; ContextVar middleware must use reset(token) not set(token)

## 1. Pitfall

Two issues surfaced during F012 Phase A review fixes:
(a) `ruff check --fix --select F401` removed re-exported imports (names imported only to be re-exported by the module), breaking downstream importers.
(b) A request-REMOVED_FIELD_id middleware reset the ContextVar by calling `bind_request_id(token)` (i.e. `set(token)`) instead of `_request_id.reset(token)` — passing a `Token` where a `str | None` was expected.

## 2. Root Cause

(a) Ruff's F401 has no notion of re-export intent; a name imported but unused *in the module* is flagged even if external code imports it from there.
(b) `ContextVar.set()` returns a `Token` and accepts a *value*, not a token. To restore a previous value you must call `ContextVar.reset(token)`. The middleware conflated the two APIs.

## 3. Trigger Conditions

(a) Running `ruff --fix --select F401` on a module that re-exports (e.g. `from x import Y` where Y is imported by other modules from *this* module).
(b) Writing a ContextVar-based middleware that captures `token = var.set(v)` in a try and tries to restore in a finally by calling `var.set(token)` instead of `var.reset(token)`.

## 4. Fix

(a) Protect re-export imports with `# noqa: F401` (or `__all__`) before running F401 auto-fix; only auto-fix truly-unused imports.
(b) Expose a `reset_request_id(token: Token) -> None` helper that calls `_request_id.reset(token)`; call it in the middleware finally block.

## 5. Guard (Executable)

- Lint: `ruff check src/` passes with no baseline ignore (F401 included) — re-exports carry `# noqa: F401`.
- Type: `mypy src/` catches the Token-vs-value arg-type mismatch (`Argument 1 to "bind_request_id" has incompatible type "Token[str | None]"; expected "str | None"`).
- Test: `src/tests/f009_api_server/test_request_id.py::test_request_id_bound_in_log_context` verifies the contextvar is correctly bound during the request.

## 6. Source Anchor

- Commit `bee3852` (F012 Phase A review fix — mypy caught the Token bug)
- `src/f007_infrastructure/logging.py` (`reset_request_id`)
- `src/f009_api_server/server.py` (`request_id_middleware`)

## 7. Related

- ADR-027 (F012 DB concurrency)
- LL-003 (propagate-then-extend duplicates — same F012 review cycle)

---

## Quality Gate Checklist

- [x] QG1: Source anchor has at least 1 entry
- [x] QG2: Timeliness verified (no subsequent addendum invalidates this)
- [x] QG3: Executable guard references a real script/test/rule (ruff + mypy + test)
- [x] QG4: Principle slot is null unless supported by a real failure case
- [x] QG5: No existing LL-XXX describes the same pitfall with the same root cause
