---
REMOVED_FIELD_id: ADR-013
title: Dialog Tracer with Animated Walkthrough
status: accepted
created: 2026-06-16
updated: 2026-06-17
decision_type: design
feature_ids: [F004]
---

# ADR-013: Dialog Tracer with Animated Walkthrough

## Context

The Cytoscape.js tree visualizer shows the full decision tree structure, but there was no way to trace how a specific real conversation maps onto the tree. Users needed to verify that real dialog paths correctly flow through the tree nodes.

## Decision

Add a dialog tracer to `tree_explorer.html` that:

1. Loads `dialog_records.json` containing all 31 call records (cache-busted with `?_=Date.now()`)
2. Provides a call selector dropdown
3. Walks through the selected call's turns sequentially
4. Highlights the corresponding path in the Cytoscape.js tree
5. Auto-play animation with flowing node highlights (1400ms per step)
6. Panel scrolls to keep the active step near the top

### Flowing Highlight Design

Only the current node glows during animation (not the full path). This avoids visual clutter on deep paths and makes the walk direction clear.

### Dialog View Toggle

A toggle button switches between full tree view and dialog-path-only view. View mode uses a dedicated `buildViewGraph` renderer (not dagre) that lays out nodes in a sequential vertical flow:

1. Walks the dialog sequence in order, assigning each first-seen node the next row (Y = row × 320)
2. Already-seen nodes (back/cycle edges) reuse their existing row
3. Back edges rendered as dashed slate lines with source offset rightward to avoid edge crossing
4. Same-row nodes spread horizontally at 280px intervals
5. Uses `preset` layout with `cy.fit(undefined, 80)` for comfortable initial zoom

### Info Panel Enhancement

Clicking a node opens a slide-in info panel showing:
- Node type, branch key, inherited facts
- Sentence pool with `collector_action` and `fact_context` tags
- Matching dialog turns highlighted and scrolled into view in the flow panel

### No-Cache HTTP Server

`serve_tree.py` uses `NoCacheHandler` (Cache-Control: no-store) and `ReusableTCPServer` (allow_reuse_address) to ensure fresh data on every page reload during development.

## Why

- Validates that real conversations correctly map to tree paths
- Provides an intuitive way to explore the tree with real data
- Auto-play makes it easy to watch the full flow without clicking each step
- Flowing highlight is cleaner than full-path highlighting on trees with depth up to 17
- Dialog view toggle isolates the traced path from tree noise
- Info panel with turn matching enables cross-referencing between tree and dialog
- No-cache server prevents stale JSON during iterative development

## Consequences

- `dialog_records.json` must be generated alongside `decision_tree.json`
- Tree explorer HTML size increased (~853 lines)
- `serve_tree.py` uses custom HTTP handler (not SimpleHTTPRequestHandler)
- All action nodes (including empathy/pressure) render as action type (diamond, amber)
- No impact on tree construction logic — tracer is purely a UI feature
