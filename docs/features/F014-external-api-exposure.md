---
id: F014
name: External API Exposure
status: review
owner: agent
related_features: [F009, F012, F013]
topics: [api, external, rest, integration]
doc_kind: spec
created: 2026-07-03
updated: 2026-07-03
spec: external_api.md
---

# F014: External API Exposure

> **Status**: review | **Owner**: agent | **Priority**: P0
>
> **Spec**: `external_api.md` — three REST endpoints for external collection systems to call the recommendation engine.
>
> **Architecture**: Wrap and reuse existing internal APIs. Extract shared core logic from SocketIO handlers into reusable functions (`_create_session`, `_run_turn`, `_end_session`). External REST endpoints are thin adapters that call the shared functions and format the response. SocketIO handlers refactored to use the same shared functions — no logic duplication.

## Why

The recommendation system currently exposes a SocketIO-based API (`start_session`, `customer_turn`, `collector_turn`, `end_session`) and an internal REST endpoint (`POST /recommend`). External collection systems (催收系统) cannot use SocketIO — they need simple REST endpoints with a request/response cycle per turn. The external API spec in `external_api.md` defines three endpoints under `/api/v1/` that external systems will call.

## What

Three REST endpoints on the existing FastAPI app, under the `/api/v1/` prefix. Each is a thin wrapper around shared functions extracted from the existing SocketIO handlers:

### Shared functions (extracted from SocketIO handlers)

| Function | Extracted from | Used by |
|---|---|---|
| `_create_session(cust_no, context, session_id=None)` | `start_session` (SocketIO) | SocketIO `start_session` + `POST /api/v1/session/start` |
| `_run_turn(session_id, utterance, conv_ctx)` | `customer_turn` (SocketIO) | SocketIO `customer_turn` + `POST /api/v1/recommend` |
| `_end_session(session_id)` | `end_session` (SocketIO) | SocketIO `end_session` + `DELETE /api/v1/session/end` |

`_run_turn` wraps the full recommendation pipeline: `extract_state` → `merge_state` → `embed_single` → `recommend` → update session → persist to DB. Both SocketIO and REST call it; SocketIO adds `sio.emit` on top, REST formats the external response.

### Endpoint 1: `POST /api/v1/session/start`

Creates a session and binds customer profile data (画像). Called once at the start of a call.

**Request**: `call_id` (session identifier), `call_info`, `agent`, `customer`, `cust_tags[]`

**Logic**: `map_cust_tags_to_context(cust_tags)` → `_create_session(cust_no, context, session_id=call_id, call_info, agent)` → 200. `call_info` and `agent` stored on the session for context.

### Endpoint 2: `POST /api/v1/recommend`

Real-time recommendation. Called once per customer turn.

**Request**: `call_id`, `current_text`, `history_context[]`

**Response**: `recommendation`, `state_tags[]`, `confidence`, `rec_id`, `info`

**Logic**: `_run_turn(call_id, current_text, " ".join(history_context + [current_text]))` → format external response (`state_tags` ← facts + emotions, `rec_id` ← `rec_{call_id}_{turn:03d}`)

### Endpoint 3: `DELETE /api/v1/session/end?call_id=...`

Ends the session. Optional — sessions expire via TTL if not called.

**Logic**: `_end_session(call_id)` → `{code: 0, message: "session closed", call_id}`

## Acceptance Criteria

### Endpoint 1: session/start
- [x] AC-1: `POST /api/v1/session/start` with valid payload → 200, session created in SessionStore + persisted to DB
- [x] AC-2: `call_id` used as session identifier (not auto-generated `sess_xxxx`)
- [x] AC-3: `cust_tags` mapped to internal `context` bitmask fields (see Tag Mapping below)
- [x] AC-4: Missing `call_id` → 422
- [x] AC-5: Oversize payload → 422 (max_length validation)

### Endpoint 2: recommend
- [x] AC-6: `POST /api/v1/recommend` with valid `call_id` + `current_text` → 200 with `recommendation`, `state_tags`, `confidence`, `rec_id`, `info`
- [x] AC-7: `recommendation` is the recommended script text (null when no match)
- [x] AC-8: `state_tags` contains extracted facts + emotions
- [x] AC-9: `confidence` is 0–1 float
- [x] AC-10: `rec_id` format is `rec_{call_id}_{turn_number:03d}` (per `external_api.md` spec)
- [x] AC-11: Unknown `call_id` (no session) → 404
- [x] AC-12: `history_context` appended to conversation context buffer
- [x] AC-13: Oversize `current_text` → 422

### Endpoint 3: session/end
- [x] AC-14: `DELETE /api/v1/session/end?call_id=...` → 200 with `code: 0`, `message`, `call_id`
- [x] AC-15: Unknown `call_id` → 404
- [x] AC-16: Missing `call_id` query param → 422

### Cross-cutting
- [x] AC-17: All three endpoints are async, reuse existing `AsyncSentenceDB` + `SessionStore` + `extract_state` + `recommend` via shared functions
- [x] AC-18: SocketIO handlers refactored to use shared functions — no logic duplication, no regression
- [x] AC-19: Rate limiting applies to `/api/v1/recommend` (reuse existing `RateLimiter`)
- [x] AC-20: Service not ready (degrade mode) → 503 on all `/api/v1/` endpoints

## Tag Mapping (cust_tags → context bitmask)

The external system sends `cust_tags` as `[{tag, value}]`. These must be mapped to the internal `BITMASK_FIELDS`:

| cust_tag.tag | BITMASK_FIELD | Value interpretation |
|---|---|---|
| 经营贷款余额 | `has_auto_loan` | float > 0 → True |
| 商业房贷余额 | `has_mortgage` | float > 0 → True |
| 持卡人当前是否缴纳社保 | `social_insurance_stable` | "是" → True, else False |
| 客户风险标识等级 | `credit_rating_good` | "1级" or "2级" → True, else False |
| 持卡用户是否疑似高风险代理投诉 | `has_complaint_history` | "是" → True, else False |
| 持卡用户是否疑似代理中介投诉 | `has_complaint_history` | "是" → True (OR with above) |

**Open question**: Some bitmask fields (`has_negotiation_history`, `card_restricted`, `is_cash_out_customer`, `has_legal_tools`, `is_negotiation_brain_customer`) have no corresponding `cust_tag`. These default to `False`.

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| KD-1 | `call_id` used directly as session_id | External system owns the identifier; avoids a mapping table |
| KD-2 | New REST routes on existing FastAPI app | No separate service; shares DB pool, SessionStore, taxonomy |
| KD-3 | Tag mapping is a pure function | Testable in isolation; easy to extend when new tags are added |
| KD-4 | `rec_id` = `rec_{call_id}_{turn:03d}` | Matches `external_api.md` spec; deterministic, traceable to call + turn |
| KD-5 | Wrap internal APIs — extract shared functions from SocketIO handlers | No logic duplication; SocketIO and REST share the same core pipeline; external endpoints are thin adapters (~5–10 lines each) |
| KD-6 | `SessionStore.create_with_id()` for caller-provided session IDs | `create()` auto-generates `sess_xxxx`; external API needs `call_id` as ID; refactor `create()` to delegate |
| KD-7 | `ExternalCustomer` models `cust_no`, `ac_no`, `called_no` | Matches `external_api.md` spec schema; all fields stored |
| KD-8 | `call_info` and `agent` stored on session dict | Spec passes meaningful call/agent metadata; preserved for analytics and routing |
| KD-9 | Session TTL default 7200s (2 hours) | Matches `external_api.md` spec: "TTL（默认2小时）" |
| KD-10 | `call_id` and `cust_tags[]` have max_length limits | AC-5 oversize payload validation; `call_id` max 8000 chars, `cust_tags` max 500 items |

## Open Questions

| # | Question | Status |
|---|---|---|
| OQ-1 | Should `/api/v1/recommend` also persist transcript turns to DB (like the SocketIO `customer_turn`)? | ⬜ Assume yes for consistency |
| OQ-2 | Should `history_context` replace or append to the conversation context buffer? | ⬜ Assume append (match SocketIO behavior) |
| OQ-3 | What should `info` field contain? Empty string by default? | ⬜ Assume empty string unless fallback/exception |
| OQ-4 | Should the external API have its own rate limit config, or reuse the existing `server.rate_limit_rps`? | ⬜ Reuse existing for now |

## Dependencies

- **Builds on**: F009 (API server), F012 (SessionStore + DB persistence), F013 (asyncpg)
- **Blocked by**: none
- **Related**: F008 (state extraction — `state_tags` come from `extract_state`)

## Risk

| Risk | Mitigation |
|------|------|
| Tag mapping is incomplete or wrong → wrong recommendations | Tag mapping is a pure function with unit tests; defaults to False for unmapped tags |
| `call_id` collision with auto-generated `sess_xxxx` IDs | `call_id` format is a long numeric string; `sess_` prefix avoids collision |
| External system sends unexpected tag values | Value interpretation is defensive (try/except, default False) |

## Links

| Type | Path | Description |
|------|------|------|
| **Spec** | `external_api.md` | External API interface specification |
| **Plan** | `docs/features/F014-implementation-plan.md` | Implementation plan — 9 TDD steps, wrap internal APIs |
| **Feature** | `docs/features/F009-api-server.md` | Existing API server |
| **Feature** | `docs/features/F012-runtime-robustness-hardening.md` | SessionStore + DB persistence |
| **Source** | `src/f009_api_server/server.py` | Current server (SocketIO handlers to extract from) |
| **Source** | `src/f009_api_server/session_store.py` | SessionStore (add `create_with_id`) |
| **Source** | `src/f005_context_scoring/scoring_metrics.py` | BITMASK_FIELDS definition |

## Files

| File | Change | Description |
|------|--------|-------------|
| `src/f009_api_server/tag_mapping.py` | New | Pure function `map_cust_tags_to_context()` |
| `src/f009_api_server/session_store.py` | Modified | Added `create_with_id()`, refactored `create()` to delegate |
| `src/f009_api_server/server.py` | Modified | Extracted `_run_turn()`, `_create_session()` (with `call_info`/`agent` storage), `_end_session()`; added 3 external endpoints + Pydantic models (`ExternalCustomer` with `cust_no`/`ac_no`/`called_no`); extended rate limiting to `/api/v1/recommend`; `rec_id` format `rec_{call_id}_{turn:03d}`; TTL default 7200s |
| `config.md` | Modified | `session_ttl: 7200` (2 hours per spec) |
| `src/tests/f009_api_server/test_tag_mapping.py` | New | 14 tests for tag mapping |
| `src/tests/f009_api_server/test_session_store.py` | Modified | 4 new tests for `create_with_id()` |
| `src/tests/f009_api_server/test_run_turn.py` | New | 5 tests for `_run_turn()` |
| `src/tests/f009_api_server/test_session_db_wiring.py` | Modified | 5 new tests for `_create_session()` / `_end_session()` |
| `src/tests/f009_api_server/test_external_api_models.py` | New | 6 tests for Pydantic models (incl. `ac_no`/`called_no`) |
| `src/tests/f009_api_server/test_external_session_start.py` | New | 7 tests for `POST /api/v1/session/start` (incl. oversize, call_info/agent storage) |
| `src/tests/f009_api_server/test_external_recommend.py` | New | 9 tests for `POST /api/v1/recommend` |
| `src/tests/f009_api_server/test_external_session_end.py` | New | 4 tests for `DELETE /api/v1/session/end` |
| `src/tests/f009_api_server/test_external_api_integration.py` | New | 3 integration + regression tests |
