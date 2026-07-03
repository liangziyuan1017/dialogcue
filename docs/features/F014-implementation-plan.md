# F014 Implementation Plan — External API Exposure

> **Feature**: F014 | **Status**: planned | **Created**: 2026-07-03
>
> **Spec**: `external_api.md` | **Feature doc**: `docs/features/F014-external-api-exposure.md`

## Overview

Add three REST endpoints under `/api/v1/` to the existing FastAPI app in `src/f009_api_server/server.py`. Each step is TDD: RED (failing test) → GREEN (minimal impl) → refactor.

## Step 1: Tag mapping function (cust_tags → context)

**Files:**
- New: `src/f009_api_server/tag_mapping.py`
- New: `src/tests/f009_api_server/test_tag_mapping.py`

**Task:** Pure function `map_cust_tags_to_context(cust_tags: list[dict]) -> dict` that converts `[{tag, value}]` to `{bitmask_field: bool}`.

**TDD:**
1. RED: Test `map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "5000.0"}])` → `{"has_auto_loan": True}`
2. RED: Test `map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "0.0"}])` → `{"has_auto_loan": False}`
3. RED: Test `map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "是"}])` → `{"social_insurance_stable": True}`
4. RED: Test `map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "1级"}])` → `{"credit_rating_good": True}`
5. RED: Test `map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "3级"}])` → `{"credit_rating_good": False}`
6. RED: Test complaint tags OR together → `has_complaint_history: True`
7. RED: Test unknown tag → ignored (no crash)
8. RED: Test empty list → `{}` (all defaults False)
9. GREEN: Implement mapping table + value interpreters
10. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_tag_mapping.py -v`

---

## Step 2: Pydantic models for external API

**Files:**
- Modified: `src/f009_api_server/server.py` (add models)
- New: `src/tests/f009_api_server/test_external_api_models.py`

**Task:** Pydantic models for the three endpoint request/response shapes.

**Models:**
- `ExternalSessionStartRequest`: `call_id` (required), `call_info`, `agent`, `customer`, `cust_tags[]`
- `ExternalRecommendRequest`: `call_id` (required), `current_text` (required, max_length), `history_context[]`
- `ExternalRecommendResponse`: `recommendation`, `state_tags[]`, `confidence`, `rec_id`, `info`
- `ExternalSessionEndResponse`: `code`, `message`, `call_id`

**TDD:**
1. RED: Test valid `ExternalSessionStartRequest` parses correctly
2. RED: Test missing `call_id` → ValidationError
3. RED: Test valid `ExternalRecommendRequest` parses correctly
4. RED: Test missing `current_text` → ValidationError
5. RED: Test oversize `current_text` (>8000 chars) → ValidationError
6. GREEN: Add models to server.py
7. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_external_api_models.py -v`

---

## Step 3: `POST /api/v1/session/start` endpoint

**Files:**
- Modified: `src/f009_api_server/server.py` (add route)
- New: `src/tests/f009_api_server/test_external_session_start.py`

**Task:** Endpoint that creates a session using `call_id` as the session ID, maps `cust_tags` to context, persists to DB.

**TDD:**
1. RED: Test `POST /api/v1/session/start` with valid payload → 200, session exists in SessionStore
2. RED: Test `call_id` is used as session_id (not auto-generated `sess_xxxx`)
3. RED: Test `cust_tags` mapped to context in session
4. RED: Test missing `call_id` → 422
5. RED: Test service not ready → 503
6. RED: Test `db.save_session` called (persistence)
7. GREEN: Implement endpoint:
   - Validate request via pydantic
   - Map `cust_tags` → context via `map_cust_tags_to_context`
   - Create session in SessionStore with `call_id` as session_id
   - Persist to DB
   - Return 200
8. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_external_session_start.py -v`

**Note:** SessionStore.create() auto-generates `sess_xxxx`. Need to either add a `create_with_id(session_id, ...)` method or use `restore()` after `create()`.

---

## Step 4: `POST /api/v1/recommend` endpoint

**Files:**
- Modified: `src/f009_api_server/server.py` (add route)
- New: `src/tests/f009_api_server/test_external_recommend.py`

**Task:** Endpoint that looks up session by `call_id`, runs extract_state + recommend, returns external response format.

**TDD:**
1. RED: Test valid request → 200 with `recommendation`, `state_tags`, `confidence`, `rec_id`, `info`
2. RED: Test `recommendation` is the script_text (null when no match)
3. RED: Test `state_tags` contains extracted facts + emotions
4. RED: Test `confidence` is 0–1 float
5. RED: Test `rec_id` format is `{call_id}_{turn:03d}`
6. RED: Test unknown `call_id` → 404
7. RED: Test `history_context` appended to conversation context buffer
8. RED: Test oversize `current_text` → 422
9. RED: Test rate limit exceeded → 429
10. RED: Test service not ready → 503
11. RED: Test transcript turn persisted to DB
12. GREEN: Implement endpoint:
    - Validate request
    - Look up session by `call_id` in SessionStore
    - If not found → 404
    - Run `extract_state(current_text, taxonomy, db)`
    - `merge_state(session.conversation_state, extraction)`
    - Build conversation_context from `history_context` + `current_text`
    - Run `recommend(...)` with bitmask, query_vec, etc.
    - Build `state_tags` from extraction facts + emotions
    - Build `rec_id` = `{call_id}_{turn:03d}`
    - Persist transcript turn + session state to DB
    - Return response
13. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_external_recommend.py -v`

---

## Step 5: `DELETE /api/v1/session/end` endpoint

**Files:**
- Modified: `src/f009_api_server/server.py` (add route)
- New: `src/tests/f009_api_server/test_external_session_end.py`

**Task:** Endpoint that ends a session by `call_id`.

**TDD:**
1. RED: Test `DELETE /api/v1/session/end?call_id=...` → 200 with `code: 0`, `message`, `call_id`
2. RED: Test unknown `call_id` → 404
3. RED: Test missing `call_id` param → 422
4. RED: Test session removed from SessionStore
5. GREEN: Implement endpoint:
   - Get `call_id` from query params
   - Look up session in SessionStore
   - If not found → 404
   - Remove session
   - Return `{code: 0, message: "session closed", call_id}`
6. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_external_session_end.py -v`

---

## Step 6: Cross-cutting concerns + integration

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_external_api_integration.py`

**Task:** Verify cross-cutting concerns work end-to-end.

**TDD:**
1. RED: Test full flow: session/start → recommend → recommend → session/end
2. RED: Test degrade mode: all `/api/v1/` endpoints return 503 when not ready
3. RED: Test external endpoints don't interfere with existing SocketIO handlers
4. RED: Test external endpoints don't interfere with existing `/recommend` endpoint
5. GREEN: Fix any issues found
6. Verify: all tests pass

**Verify:** `pytest src/tests/f009_api_server/test_external_api_integration.py -v`

---

## Step 7: Full regression + lint

**Task:** Run full test suite + ruff + mypy to verify no regressions.

**Commands:**
```bash
.venv/bin/python -m pytest src/tests/ -q
.venv/bin/ruff check src/
.venv/bin/mypy src/ --ignore-missing-imports
```

**Success criteria:** All tests pass, ruff clean, mypy clean (no new errors).

---

## Summary

| Step | Files | Tests | ACs |
|------|-------|-------|-----|
| 1: Tag mapping | 2 new | 8 | AC-3 |
| 2: Pydantic models | 1 mod, 1 new | 5 | AC-4, AC-5, AC-13 |
| 3: session/start | 1 mod, 1 new | 6 | AC-1, AC-2, AC-3, AC-4, AC-5, AC-20 |
| 4: recommend | 1 mod, 1 new | 12 | AC-6–AC-13, AC-19, AC-20 |
| 5: session/end | 1 mod, 1 new | 4 | AC-14–AC-16, AC-20 |
| 6: Integration | 1 mod, 1 new | 4 | AC-17, AC-18, AC-20 |
| 7: Regression | — | — | All |

**Total:** ~39 new tests, 7 steps, all TDD.
