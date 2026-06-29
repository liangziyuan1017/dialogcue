# F010 — API Mock + System Status UI Implementation Plan

**Feature:** F010 — `docs/features/F010-api-mock-system-status-ui.md`
**Goal:** Replace `interactive.py` CLI with a web UI at `/ui` that provides Postman-style request building, Socket.IO session management, and pipeline trace inspection — all on the same FastAPI server with no build step.
**Acceptance Criteria:**
- `/ui` serves the HTML page with all three panels
- REST mock panel: can construct and send a `POST /recommend` request, see JSON response
- Socket.IO panel: can start/customer/collector/end a session, see live transcript
- Pipeline trace panel: `POST /recommend/debug` returns per-step trace data
- Sentence pool inspector: shows candidate sentences with scores for a debug call
- CodeMirror 6 loaded for JSON editing
- Tailwind CSS loaded for styling
- No build step — static files served directly by FastAPI
- Same server/port as F009

**Architecture:** F010 extends the existing F009 FastAPI server. A new `src/f010_api_mock_ui/` module provides a `POST /recommend/debug` endpoint that wraps the recommend pipeline to capture per-step trace data (state extraction, merge, path lookup, vector search, ranking). Static HTML/JS/CSS files are served via `StaticFiles` mount at `/ui`. Vanilla JS only — no npm, no build step. CodeMirror 6 and Tailwind via CDN.

**Tech Stack:** FastAPI StaticFiles, Vanilla JS, CodeMirror 6 (CDN), Tailwind CSS (CDN), Socket.IO client (bundled)

---

### Task 1: Module skeleton + debug trace data structure

**Files:**
- Create: `src/f010_api_mock_ui/__init__.py`
- Create: `src/f010_api_mock_ui/debug.py`
- Test: `src/tests/f010_api_mock_ui/test_debug.py`

**Step 1: Write the failing test** — test that `debug_recommend()` returns a dict with `trace` (list of step dicts with `step`, `input`, `output`, `latency_ms` keys), `candidates` (list), and `recommendation` (dict or None).
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — `debug_recommend()` function that calls each pipeline step individually and captures input/output/latency for each: (1) extract_state, (2) merge_state, (3) compute_bitmask, (4) embed, (5) recommend, (6) build response. Return structured trace.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): add debug trace data structure`

---

### Task 2: Debug endpoint route

**Files:**
- Modify: `src/f010_api_mock_ui/debug.py`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f010_api_mock_ui/test_debug_endpoint.py`

**Step 1: Write the failing test** — test that `POST /recommend/debug` returns 200 with trace structure. Use FastAPI TestClient.
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — add `POST /recommend/debug` route to server.py that calls `debug_recommend()` and returns the trace. Import from f010 module.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): add /recommend/debug endpoint`

---

### Task 3: UI HTML shell + StaticFiles mount

**Files:**
- Create: `src/f010_api_mock_ui/ui/index.html`
- Create: `src/f010_api_mock_ui/ui/app.js`
- Create: `src/f010_api_mock_ui/ui/style.css`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f010_api_mock_ui/test_ui_served.py`

**Step 1: Write the failing test** — test that `GET /ui/` returns 200 and HTML containing the three panel containers.
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — create `index.html` with three panel sections (rest-mock, socket-session, pipeline-trace), empty `app.js`, minimal `style.css`. Mount `StaticFiles(directory=..., html=True)` at `/ui` in server.py.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): add UI shell with StaticFiles mount`

---

### Task 4: REST mock panel

**Files:**
- Modify: `src/f010_api_mock_ui/ui/index.html`
- Modify: `src/f010_api_mock_ui/ui/app.js`
- Modify: `src/f010_api_mock_ui/ui/style.css`
- Test: `src/tests/f010_api_mock_ui/test_ui_rendering.py`

**Step 1: Write the failing test** — test that the REST mock panel HTML contains: URL display, method selector, CodeMirror editor container, send button, response viewer container.
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — add REST mock panel HTML structure with CodeMirror 6 CDN script. Add JS to: initialize CodeMirror on a textarea, send `POST /recommend` via fetch on button click, display JSON response with syntax highlighting. Add CSS for panel layout.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): implement REST mock panel`

---

### Task 5: Socket.IO session panel

**Files:**
- Modify: `src/f010_api_mock_ui/ui/index.html`
- Modify: `src/f010_api_mock_ui/ui/app.js`
- Modify: `src/f010_api_mock_ui/ui/style.css`
- Test: `src/tests/f010_api_mock_ui/test_ui_rendering.py`

**Step 1: Write the failing test** — test that the Socket.IO panel HTML contains: start/customer/collector/end buttons, transcript container, state display container.
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — add Socket.IO panel HTML. Add JS to: connect Socket.IO client, emit events on button clicks, display transcript and conversation_state updates from server responses. Bundle socket.io.min.js from node_modules or CDN.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): implement Socket.IO session panel`

---

### Task 6: Pipeline trace panel + sentence pool inspector

**Files:**
- Modify: `src/f010_api_mock_ui/ui/index.html`
- Modify: `src/f010_api_mock_ui/ui/app.js`
- Modify: `src/f010_api_mock_ui/ui/style.css`
- Modify: `src/f010_api_mock_ui/debug.py`
- Test: `src/tests/f010_api_mock_ui/test_ui_rendering.py`
- Test: `src/tests/f010_api_mock_ui/test_debug.py`

**Step 1: Write the failing test** — test that trace panel HTML contains: trace steps container, sentence pool table. Test that `debug_recommend()` trace includes `candidates` with `script_id`, `script_text`, `final_score`, `win_rate`, `sas`, `vec_score`.
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — add trace panel HTML. Add JS to: send `POST /recommend/debug`, render each trace step as a collapsible card (step name, latency, input/output JSON), render candidate sentences in a sortable table. Enhance `debug_recommend()` to include candidate sentences from the retrieval step.
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F010): implement pipeline trace panel with sentence pool inspector`

---

### Task 7: Tailwind styling + polish

**Files:**
- Modify: `src/f010_api_mock_ui/ui/index.html`
- Modify: `src/f010_api_mock_ui/ui/style.css`

**Step 1: Add Tailwind CDN** — add `<script src="https://cdn.tailwindcss.com"></script>` to index.html `<head>`.
**Step 2: Apply Tailwind classes** — replace custom CSS with Tailwind utility classes for layout (grid/flex), spacing, typography, colors. Keep `style.css` only for CodeMirror overrides and custom animations.
**Step 3: Verify UI renders** — manual check that all three panels display correctly.
**Step 4: Commit** — `feat(F010): add Tailwind styling`

---

### Task 8: Update feature doc + README

**Files:**
- Modify: `docs/features/F010-api-mock-system-status-ui.md`
- Modify: `src/README.md`

**Step 1: Update feature doc** — set `status: planned`, add `## Implementation Plan` section linking to this plan, check off completed AC items.
**Step 2: Update src/README.md** — add f010_api_mock_ui/ row to the Feature Modules table.
**Step 3: Commit** — `docs(F010): update feature doc and README`
