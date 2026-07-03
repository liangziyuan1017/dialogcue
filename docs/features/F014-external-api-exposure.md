---
id: F014
name: External API Exposure
status: planned
owner: agent
related_features: [F009, F012, F013]
topics: [api, external, rest, integration]
doc_kind: spec
created: 2026-07-03
updated: 2026-07-03
spec: external_api.md
---

# F014: External API Exposure

> **Status**: draft | **Owner**: agent | **Priority**: P0
>
> **Spec**: `external_api.md` — three REST endpoints for external collection systems to call the recommendation engine.

## Why

The recommendation system currently exposes a SocketIO-based API (`start_session`, `customer_turn`, `collector_turn`, `end_session`) and an internal REST endpoint (`POST /recommend`). External collection systems (催收系统) cannot use SocketIO — they need simple REST endpoints with a request/response cycle per turn. The external API spec in `external_api.md` defines three endpoints under `/api/v1/` that external systems will call.

## What

Three REST endpoints on the existing FastAPI app, under the `/api/v1/` prefix:

### Endpoint 1: `POST /api/v1/session/start`

Creates a session and binds customer profile data (画像). Called once at the start of a call.

**Request**: `call_id` (session identifier), `call_info`, `agent`, `customer`, `cust_tags[]`

**Mapping**: `cust_tags` → internal `context` dict (bitmask fields). `call_id` → session identifier (used directly, not auto-generated).

### Endpoint 2: `POST /api/v1/recommend`

Real-time recommendation. Called once per customer turn.

**Request**: `call_id`, `current_text`, `history_context[]`

**Response**: `recommendation`, `state_tags[]`, `confidence`, `rec_id`, `info`

**Mapping**: `current_text` → customer utterance → `extract_state` + `recommend`. `state_tags` ← extracted facts + emotions. `rec_id` ← `{call_id}_{turn_number}`.

### Endpoint 3: `DELETE /api/v1/session/end?call_id=...`

Ends the session. Optional — sessions expire via TTL if not called.

**Response**: `code`, `message`, `call_id`

## Acceptance Criteria

### Endpoint 1: session/start
- [ ] AC-1: `POST /api/v1/session/start` with valid payload → 200, session created in SessionStore + persisted to DB
- [ ] AC-2: `call_id` used as session identifier (not auto-generated `sess_xxxx`)
- [ ] AC-3: `cust_tags` mapped to internal `context` bitmask fields (see Tag Mapping below)
- [ ] AC-4: Missing `call_id` → 422
- [ ] AC-5: Oversize payload → 422 (max_length validation)

### Endpoint 2: recommend
- [ ] AC-6: `POST /api/v1/recommend` with valid `call_id` + `current_text` → 200 with `recommendation`, `state_tags`, `confidence`, `rec_id`, `info`
- [ ] AC-7: `recommendation` is the recommended script text (null when no match)
- [ ] AC-8: `state_tags` contains extracted facts + emotions
- [ ] AC-9: `confidence` is 0–1 float
- [ ] AC-10: `rec_id` format is `{call_id}_{turn_number:03d}`
- [ ] AC-11: Unknown `call_id` (no session) → 404
- [ ] AC-12: `history_context` appended to conversation context buffer
- [ ] AC-13: Oversize `current_text` → 422

### Endpoint 3: session/end
- [ ] AC-14: `DELETE /api/v1/session/end?call_id=...` → 200 with `code: 0`, `message`, `call_id`
- [ ] AC-15: Unknown `call_id` → 404
- [ ] AC-16: Missing `call_id` query param → 422

### Cross-cutting
- [ ] AC-17: All three endpoints are async, use existing `AsyncSentenceDB` + `SessionStore`
- [ ] AC-18: Endpoints do not interfere with existing SocketIO handlers or `/recommend` endpoint
- [ ] AC-19: Rate limiting applies to `/api/v1/recommend` (reuse existing `RateLimiter`)
- [ ] AC-20: Service not ready (degrade mode) → 503 on all `/api/v1/` endpoints

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
| KD-4 | `rec_id` = `{call_id}_{turn:03d}` | Deterministic, traceable to call + turn |

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
| **Feature** | `docs/features/F009-api-server.md` | Existing API server |
| **Feature** | `docs/features/F012-runtime-robustness-hardening.md` | SessionStore + DB persistence |
| **Source** | `src/f009_api_server/server.py` | Current server implementation |
| **Source** | `src/f005_context_scoring/scoring_metrics.py` | BITMASK_FIELDS definition |
