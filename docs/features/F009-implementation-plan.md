# F009: REST API + Socket.IO Server — Implementation Plan

**Feature:** F009 — `docs/features/F009-api-server.md`
**Goal:** Create FastAPI server with `POST /recommend` endpoint and Socket.IO session management per [F009-api-server.md](F009-api-server.md).
**Acceptance Criteria:** See F009 feature doc
**Architecture:** FastAPI for REST, python-socketio for WebSocket sessions. `/recommend` wires the full pipeline: state extraction → accumulation → path signature → node lookup → bitmask filter → vector match → rank → return top-1. Socket.IO manages session state automatically.
**Tech Stack:** Python, FastAPI, uvicorn, python-socketio, asyncio

---

### Task 1: FastAPI App + /recommend Endpoint

**Files:**
- Create: `src/f009_api_server/__init__.py`
- Create: `src/f009_api_server/server.py`
- Test: `src/tests/api/test_recommend.py`

**Step 1:** Write failing test for `POST /recommend` — valid input returns 200 with output schema, missing fields return 400.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement FastAPI app with `/recommend` endpoint. Wire: `extract_state()` → `merge_state()` → path signature → `recommend()` → return REMOVED_FIELD_result with updated `conversation_state`.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 2: Socket.IO Session Management

**Files:**
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/api/test_socket.py`

**Step 1:** Write failing test for Socket.IO `start_session` → `customer_turn` → `collector_turn` → `end_session` flow. Test that state accumulates automatically across turns.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement Socket.IO event handlers: `start_session` (init state), `customer_turn` (extract + recommend), `collector_turn` (extract actions), `end_session` (return transcript). Session state stored in server-side dict.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 3: Error Handling + Edge Cases

**Files:**
- Modify: `src/f009_api_server/server.py`
- Modify: `src/tests/api/test_recommend.py`

**Step 1:** Write failing tests for error cases: server down (503), invalid JSON (400), empty utterance (422).

**Step 2:** Run test to verify it fails.

**Step 3:** Implement error handlers with appropriate HTTP status codes and error messages.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

## Config Externalization (F011)

Server-level parameters now configurable via `config.md`:

| Parameter | config.md key | Default |
|-----------|--------------|---------|
| embed fallback penalty | `confidence.embed_fallback_penalty` | 0.1 |
| LLM model | `llm.model` | deepseek-chat |
| LLM API base | `llm.api_base` | https://api.deepseek.com |
| LLM temperature | `llm.temperature` | 0.1 |
| Embedding model | `embedding.model` | bge-m3 |
| Embedding dimension | `embedding.dimension` | 1024 |
