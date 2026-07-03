# F014 Implementation Plan — External API Exposure

> **Feature**: F014 | **Status**: planned | **Created**: 2026-07-03
>
> **Spec**: `external_api.md` | **Feature doc**: `docs/features/F014-external-api-exposure.md`
>
> **Principle**: Wrap and reuse existing internal APIs. Extract shared core logic from SocketIO handlers into reusable functions. External REST endpoints are thin adapters that call the shared functions and format the response.

## Reuse Map

| External endpoint | Reuses | Shared function |
|---|---|---|
| `POST /api/v1/session/start` | `SessionStore.create()` + `_persist_session()` | `_create_session(cust_no, context, session_id=None)` |
| `POST /api/v1/recommend` | `extract_state()` + `merge_state()` + `recommend()` + `_compute_bitmask()` + `embed_single()` + DB persist | `_run_turn(session_id, utterance, conv_ctx)` |
| `DELETE /api/v1/session/end` | `SessionStore.remove()` | `_end_session(session_id)` |

**Key change**: Extract the inline logic from `customer_turn` (server.py:362–410) into `_run_turn()`. Both `customer_turn` (SocketIO) and `/api/v1/recommend` (REST) call it. The SocketIO handler adds `sio.emit` on top; the REST handler formats the external response.

## Step 1: Tag mapping function (cust_tags → context)

**Files:**
- New: `src/f009_api_server/tag_mapping.py`
- New: `src/tests/f009_api_server/test_tag_mapping.py`

**Task:** Pure function `map_cust_tags_to_context(cust_tags: list[dict]) -> dict` that converts `[{tag, value}]` to `{bitmask_field: bool}`.

**TDD:**
1. RED: `map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "5000.0"}])` → `{"has_auto_loan": True}`
2. RED: `map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "0.0"}])` → `{"has_auto_loan": False}`
3. RED: `map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "是"}])` → `{"social_insurance_stable": True}`
4. RED: `map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "1级"}])` → `{"credit_rating_good": True}`
5. RED: `map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "3级"}])` → `{"credit_rating_good": False}`
6. RED: complaint tags OR together → `has_complaint_history: True`
7. RED: unknown tag → ignored
8. RED: empty list → `{}`
9. GREEN: Implement mapping table + value interpreters
10. Verify

**Verify:** `pytest src/tests/f009_api_server/test_tag_mapping.py -v`

---

## Step 2: SessionStore.create_with_id()

**Files:**
- Modified: `src/f009_api_server/session_store.py`
- Modified: `src/tests/f009_api_server/test_session_store.py`

**Task:** Add `create_with_id(session_id, cust_no, context)` — same as `create()` but uses the caller-provided `session_id` instead of auto-generating `sess_xxxx`. This lets the external API use `call_id` directly.

**TDD:**
1. RED: `store.create_with_id("call_123", "c1", {})` → session exists with `store.get("call_123")`
2. RED: Test cap enforcement still applies
3. RED: Test TTL eviction still applies
4. GREEN: Refactor `create()` to delegate to `create_with_id()` with an auto-generated ID
5. Verify existing `test_session_store.py` still passes (no regression)

**Verify:** `pytest src/tests/f009_api_server/test_session_store.py -v`

---

## Step 3: Extract shared `_run_turn()` from `customer_turn`

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_run_turn.py`

**Task:** Extract the core logic from `customer_turn` (lines 362–410) into a reusable async function:

```python
async def _run_turn(session_id: str, utterance: str, conv_ctx: str) -> dict | None:
    """Core recommendation logic shared by SocketIO customer_turn and external REST /api/v1/recommend.

    Returns dict with: extraction, merged, rec_result, latency_ms, entry
    or None if session not found.
    """
```

This function:
- Looks up session by `session_id` → None if not found
- Acquires `sessions.lock(session_id)`
- Calls `extract_state()` → `merge_state()` → `embed_single()` → `recommend()`
- Updates `session["conversation_state"]`, `session["transcript"]`, `session["conversation_context_buffer"]`
- Persists to DB (`append_transcript_turn` + `save_session`)
- Returns `{extraction, merged, rec_result, latency_ms, entry}`

**Refactor `customer_turn`** to call `_run_turn()` then format the SocketIO response + `sio.emit`.

**TDD:**
1. RED: Test `_run_turn()` with valid session → returns dict with extraction, merged, rec_result
2. RED: Test `_run_turn()` with unknown session → None
3. RED: Test session conversation_state updated
4. RED: Test transcript entry appended
5. RED: Test DB persistence called
6. GREEN: Extract function, refactor `customer_turn` to use it
7. Verify: existing `test_socket.py` + `test_session_db_wiring.py` still pass (no regression)

**Verify:** `pytest src/tests/f009_api_server/test_run_turn.py src/tests/f009_api_server/test_socket.py src/tests/f009_api_server/test_session_db_wiring.py -v`

---

## Step 4: Extract shared `_create_session()` and `_end_session()`

**Files:**
- Modified: `src/f009_api_server/server.py`
- Modified: `src/tests/f009_api_server/test_session_db_wiring.py`

**Task:** Extract session creation and ending into reusable functions:

```python
async def _create_session(cust_no: str, context: dict, session_id: str | None = None) -> str:
    """Create session in SessionStore + persist to DB.
    If session_id is None, auto-generate (SocketIO behavior).
    Returns session_id.
    """

def _end_session(session_id: str) -> dict | None:
    """Remove session from SessionStore. Returns session dict or None."""
    return sessions.remove(session_id)
```

**Refactor** `start_session` (SocketIO) to call `_create_session()`. Refactor `end_session` (SocketIO) to call `_end_session()`.

**TDD:**
1. RED: Test `_create_session("c1", {"k": "v"}, session_id="call_123")` → returns `"call_123"`, session in store
2. RED: Test `_create_session("c1", {})` → auto-generates `sess_xxxx`
3. RED: Test `_create_session` persists to DB
4. RED: Test `_end_session("call_123")` → returns session dict, removed from store
5. RED: Test `_end_session("unknown")` → None
6. GREEN: Extract functions, refactor SocketIO handlers
7. Verify: existing tests still pass

**Verify:** `pytest src/tests/f009_api_server/test_session_db_wiring.py src/tests/f009_api_server/test_socket.py -v`

---

## Step 5: Pydantic models for external API

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_external_api_models.py`

**Task:** Pydantic models for the external request/response shapes.

**Models:**
- `ExternalSessionStartRequest`: `call_id` (required), `call_info`, `agent`, `customer`, `cust_tags[]`
- `ExternalRecommendRequest`: `call_id` (required), `current_text` (required, max_length), `history_context[]`

**TDD:**
1. RED: Valid `ExternalSessionStartRequest` parses
2. RED: Missing `call_id` → ValidationError
3. RED: Valid `ExternalRecommendRequest` parses
4. RED: Missing `current_text` → ValidationError
5. RED: Oversize `current_text` → ValidationError
6. GREEN: Add models
7. Verify

**Verify:** `pytest src/tests/f009_api_server/test_external_api_models.py -v`

---

## Step 6: `POST /api/v1/session/start` — thin wrapper

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_external_session_start.py`

**Task:** Thin endpoint that maps external request → calls `_create_session()` → returns 200.

**Logic:**
```
validate request (pydantic)
context = map_cust_tags_to_context(req.cust_tags)
session_id = await _create_session(req.customer.cust_no, context, session_id=req.call_id)
return {"call_id": session_id}
```

**TDD:**
1. RED: Valid payload → 200, session in SessionStore
2. RED: `call_id` used as session_id
3. RED: `cust_tags` mapped to context
4. RED: Missing `call_id` → 422
5. RED: Not ready → 503
6. GREEN: Implement (5 lines of logic)
7. Verify

**Verify:** `pytest src/tests/f009_api_server/test_external_session_start.py -v`

---

## Step 7: `POST /api/v1/recommend` — thin wrapper

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_external_recommend.py`

**Task:** Thin endpoint that calls `_run_turn()` and formats the external response.

**Logic:**
```
validate request (pydantic)
conv_ctx = " ".join(req.history_context + [req.current_text])
result = await _run_turn(req.call_id, req.current_text, conv_ctx)
if result is None: → 404
turn = result["entry"]["turn"]
rec_id = f"{req.call_id}_{turn:03d}"
state_tags = result["extraction"].get("facts", []) + result["extraction"].get("emotions", [])
recommendation = result["rec_result"].get("script_text") if result["rec_result"] else None
return {recommendation, state_tags, confidence, rec_id, info: ""}
```

**TDD:**
1. RED: Valid request → 200 with `recommendation`, `state_tags`, `confidence`, `rec_id`, `info`
2. RED: `recommendation` is script_text (null when no match)
3. RED: `state_tags` = facts + emotions
4. RED: `rec_id` = `{call_id}_{turn:03d}`
5. RED: Unknown `call_id` → 404
6. RED: `history_context` included in conv_ctx
7. RED: Oversize `current_text` → 422
8. RED: Rate limit → 429
9. RED: Not ready → 503
10. GREEN: Implement (~10 lines of logic)
11. Verify

**Verify:** `pytest src/tests/f009_api_server/test_external_recommend.py -v`

---

## Step 8: `DELETE /api/v1/session/end` — thin wrapper

**Files:**
- Modified: `src/f009_api_server/server.py`
- New: `src/tests/f009_api_server/test_external_session_end.py`

**Task:** Thin endpoint that calls `_end_session()`.

**Logic:**
```
call_id = query param
session = _end_session(call_id)
if session is None: → 404
return {code: 0, message: "session closed", call_id}
```

**TDD:**
1. RED: Valid `call_id` → 200 with `code: 0`, `message`, `call_id`
2. RED: Unknown `call_id` → 404
3. RED: Missing `call_id` → 422
4. RED: Session removed from store
5. GREEN: Implement (3 lines of logic)
6. Verify

**Verify:** `pytest src/tests/f009_api_server/test_external_session_end.py -v`

---

## Step 9: Integration + regression

**Files:**
- New: `src/tests/f009_api_server/test_external_api_integration.py`

**TDD:**
1. RED: Full flow: session/start → recommend → recommend → session/end
2. RED: External endpoints don't break SocketIO handlers
3. RED: External endpoints don't break `/recommend` endpoint
4. GREEN: Fix any issues
5. Full suite: `pytest src/tests/ -q`
6. Lint: `ruff check src/` + `mypy src/ --ignore-missing-imports`

**Verify:** All tests pass, ruff clean, mypy clean (no new errors).

---

## Summary

| Step | What | Reuses | New code |
|------|------|--------|----------|
| 1: Tag mapping | `cust_tags` → context | — | ~30 lines (pure function) |
| 2: `create_with_id()` | SessionStore | `create()` logic | ~5 lines (refactor) |
| 3: `_run_turn()` | Extract from `customer_turn` | `extract_state`, `merge_state`, `recommend`, `embed_single`, `_compute_bitmask`, DB persist | ~0 lines (move, not copy) |
| 4: `_create_session()` / `_end_session()` | Extract from `start_session` / `end_session` | `SessionStore`, `_persist_session` | ~0 lines (move) |
| 5: Pydantic models | Request validation | — | ~20 lines |
| 6: `session/start` | Thin wrapper | `_create_session()`, `map_cust_tags_to_context` | ~5 lines |
| 7: `recommend` | Thin wrapper | `_run_turn()` | ~10 lines |
| 8: `session/end` | Thin wrapper | `_end_session()` | ~3 lines |
| 9: Integration | E2E + regression | All | Tests only |

**Total:** ~70 lines of new code, ~40 tests, 9 steps, all TDD.
**SocketIO handlers refactored** to use shared functions — no logic duplication.
