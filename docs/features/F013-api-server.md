---
name: F013
title: REST API + Socket.IO Server
status: planned
depends_on: [F010, F011, F012]
created: 2026-06-24
updated: 2026-06-24
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F013: REST API + Socket.IO Server

## Goal

Create FastAPI server with `POST /recommend` endpoint and Socket.IO session management per `api_socket.md`.

Covers **Steps 8-9** of `stepwise_modification.md`.

## Passing Criteria

- `POST /recommend` returns 200 with valid output schema
- Missing required fields → 400
- `conversation_state` accumulation across multiple calls
- Socket.IO `start_session` → `customer_turn` → `end_session` flow
- State accumulation is automatic in Socket.IO sessions
- `collector_turn` extracts actions

## Files

- NEW: `src/api/__init__.py`
- NEW: `src/api/server.py`
- NEW: `src/tests/api/test_recommend.py`
- NEW: `src/tests/api/test_socket.py`
