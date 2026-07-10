---
id: F010
name: API Mock + System Status UI
phase: tooling
status: complete
worktree: ../icbc-f010-infra-layer-f010
branch: feat/f010-api-mock-ui
owner: agent
related:
  - F009
  - F004
adr: ADR-025
---

# F010 — API Mock + System Status UI

## Why

The `interactive.py` CLI is the only way to test the `/recommend` endpoint manually. Developers need a visual, Postman-style tool that also shows the pipeline internals (per-step trace, sentence pool) — without switching tools or reading raw JSON.

## What

A web UI served at `/ui` on the same FastAPI server/port (no CORS, no separate build). Three panels:

1. **REST mock panel** — Postman-style manual request builder for `POST /recommend`. Editable JSON body with CodeMirror 5.65.18, send button, response viewer with syntax highlighting.
2. **Socket.IO session panel** — stateful session interface. Start session → customer turn → collector turn → end session, with live transcript and state accumulation display.
3. **Pipeline trace panel** — shows 6 pipeline steps (input → output) for a single debug call, plus a sentence pool inspector showing the top-20 candidate sentences with scores.

A dedicated `POST /recommend/debug` endpoint returns the full per-step trace data.

> **Note:** The feature name retains "System Status" from the original design, but the system-status/health panel was descoped — the shipped UI is API Mock + Pipeline Trace + Sentence Pool Inspector.

## Architecture (ADR-025)

- Vanilla JS + CSS (no build step, no npm)
- FastAPI `StaticFiles` mount at `/ui` (registered in `f009/server.py:338`)
- CodeMirror 5.65.18 via CDN for JSON editing
- Tailwind CSS via CDN (Play) for styling
- Socket.IO client via CDN (v4.7.5) matching server-side python-socketio
- Same server/port as F009 — zero CORS issues

## Acceptance Criteria

- [x] `/ui` serves the HTML page with all three panels
- [x] REST mock panel: can construct and send a `POST /recommend` request, see JSON response
- [x] Socket.IO panel: can start/customer/collector/end a session, see live transcript
- [x] Pipeline trace panel: `POST /recommend/debug` returns per-step trace data (6 steps)
- [x] Sentence pool inspector: shows top-20 candidate sentences with scores for a debug call
- [x] CodeMirror 5.65.18 loaded for JSON editing
- [x] Tailwind CSS loaded for styling
- [x] No build step — static files served directly by FastAPI
- [x] Same server/port as F009

## Dependencies

- F009 (API server) — F010 extends the same FastAPI app; `/ui` mount and `/recommend/debug` route are registered in `f009/server.py` (lines 319, 338) for ASGI app ownership, with F010 supplying `debug.py` + static `ui/` assets
- F004 (Decision Tree) — F010's trace panel reuses tree data structures

## Files

| Path | Description |
|------|-------------|
| `src/f010_api_mock_ui/` | Feature module root |
| `src/f010_api_mock_ui/ui/` | Static HTML/JS/CSS files |
| `src/f010_api_mock_ui/ui/index.html` | Main UI page with three panels |
| `src/f010_api_mock_ui/ui/app.js` | Application logic |
| `src/f010_api_mock_ui/ui/style.css` | Custom styles (Tailwind via CDN) |
| `src/f010_api_mock_ui/debug.py` | Debug endpoint logic (per-step trace) |

## Design Decisions

- Used CodeMirror 5.65.18 via CDN (not 6.x) for simpler setup — single JS file, no module bundler needed
- Socket.IO client loaded from CDN (v4.7.5) matching server-side python-socketio
- Trace captures 6 pipeline steps: `extract_state`, `merge_state`, `compute_bitmask`, `embed`, `recommend`, `rank_all_candidates`
- Sentence pool inspector renders the full top-20 candidate list with scores (row 0 highlighted as the recommendation)
- Dark theme by default matching the F004 tree explorer aesthetic
- System-status/health panel was descoped — not implemented in the shipped UI
- **Editable customer background in session panel**: The Socket.IO Session panel now has an editable "Customer Background (context)" textarea (CodeMirror-backed) with a default context pre-filled (bitmask + bg_boost fields). The context is parsed and sent as `context` in the `start_session` payload. The field becomes read-only after session start and re-enables when the session ends. Previously, the session always started with `context: {}` (hardcoded empty), ignoring customer background entirely.

## Implementation Plan

See [F010-implementation-plan.md](./F010-implementation-plan.md) — 8 tasks covering debug endpoint, UI shell, REST mock panel, Socket.IO panel, pipeline trace panel, styling, and doc updates.
