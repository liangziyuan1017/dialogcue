---
REMOVED_FIELD_id: ADR-025
title: F010 UI Architecture — Vanilla JS + FastAPI StaticFiles
status: accepted
date: 2026-06-26
related: [F010]
---

## Context

F010 needs a web UI for API mocking + system status visualization. Must decide frontend tech, serving strategy, and layout.

## Decision

- **Frontend**: Vanilla JS + CSS (no build step), matching the tree_explorer pattern in f004/ui/
- **JSON editor**: CodeMirror 5.65.18 via CDN (not 6.x — single JS file, no module bundler)
- **CSS**: Tailwind CDN (Play) for utility classes
- **Serving**: FastAPI StaticFiles mount at /ui (same server/port as API), registered in f009/server.py
- **Layout**: 3-panel split — left=request builder, right-top=response, right-bottom=pipeline trace+pool
- **Socket.IO client**: via CDN (v4.7.5), not bundled locally
- **Debug endpoint**: POST /recommend/debug returns full pipeline trace (6 steps) + top-20 candidate pool in one call
- **Directory**: src/f010_api_mock_ui/

## Rationale

- No build step = zero toolchain complexity, matches existing pattern
- Same server = simplest deployment, no CORS or proxy config
- One debug call = fewer round-trips, simpler client logic
- Socket.IO via CDN = simpler than bundling; acceptable for a dev/debug tool

## Consequences

- No component model (vanilla JS). Acceptable for this scope — UI is tooling, not product.
- Tailwind CDN adds ~10KB network load. Acceptable for a dev/debug tool.
- /recommend/debug endpoint must be added to server.py.
- System-status/health panel was descoped — not implemented.
