---
id: F010
name: API Mock + System Status UI
phase: tooling
status: in-progress
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

1. **REST mock panel** — Postman-style manual request builder for `POST /recommend`. Editable JSON body with CodeMirror 6, send button, response viewer with syntax highlighting.
2. **Socket.IO session panel** — stateful session interface. Start session → customer turn → collector turn → end session, with live transcript and state accumulation display.
3. **Pipeline trace panel** — shows all 7 pipeline steps (input → output) for a single debug call, plus a sentence pool inspector showing candidate sentences with scores.

A dedicated `POST /recommend/debug` endpoint returns the full per-step trace data.

## Architecture (ADR-025)

- Vanilla JS + CSS (no build step, no npm)
- FastAPI `StaticFiles` mount at `/ui`
- CodeMirror 6 via CDN for JSON editing
- Tailwind CSS via CDN for styling
- Bundled Socket.IO client (same library as server)
- Same server/port as F009 — zero CORS issues

## Acceptance Criteria

- [ ] `/ui` serves the HTML page with all three panels
- [ ] REST mock panel: can construct and send a `POST /recommend` request, see JSON response
- [ ] Socket.IO panel: can start/customer/collector/end a session, see live transcript
- [ ] Pipeline trace panel: `POST /recommend/debug` returns per-step trace data
- [ ] Sentence pool inspector: shows candidate sentences with scores for a debug call
- [ ] CodeMirror 6 loaded for JSON editing
- [ ] Tailwind CSS loaded for styling
- [ ] No build step — static files served directly by FastAPI
- [ ] Same server/port as F009

## Dependencies

- F009 (API server) — F010 extends the same FastAPI app
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

## Implementation Plan

See [F010-implementation-plan.md](./F010-implementation-plan.md) — 8 tasks covering debug endpoint, UI shell, REST mock panel, Socket.IO panel, pipeline trace panel, styling, and doc updates.
