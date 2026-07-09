---
name: tree-ui
description: Use when building, running, or modifying the Decision Tree Explorer UI — the interactive Cytoscape.js visualization for the scored decision tree with dialog tracing. Use ONLY for the tree_explorer.html, serve_tree.py, or the tree visualization pipeline. Not for general web UI work.
---

# Decision Tree Explorer UI

Interactive visualization of the scored decision tree (`decision_tree_scored.json`) with animated dialog tracing against `dialog_records.json`.

## Architecture

```
src/ui/tree_explorer.html   ← single-file SPA (Cytoscape.js + dagre layout)
src/ui/cytoscape.min.js     ← bundled Cytoscape.js (offline)
src/ui/cytoscape-dagre.min.js ← bundled dagre layout plugin
src/ui/dagre.min.js         ← bundled dagre graph layout
src/serve_tree.py           ← HTTP server (port 8420, no-cache headers)
```

Data sources (fetched via relative HTTP):
- `../f005_context_scoring/decision_tree_scored.json` — the scored tree
- `../f004_decision_tree/dialog_records.json` — dialog records for tracing

## Running

```bash
python src/serve_tree.py
# Opens browser to http://localhost:8420/ui/tree_explorer.html
```

Server uses `NoCacheHandler` to prevent stale JSON caching. Port is 8420. `ReusableTCPServer` allows quick restarts.

## Design System

### Color Palette (CSS custom properties)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0f172a` | Page background (slate-900) |
| `--surface` | `#1e293b` | Panel backgrounds (slate-800) |
| `--border` | `#334155` | Borders (slate-700) |
| `--text` | `#f1f5f9` | Primary text (slate-50) |
| `--muted` | `#94a3b8` | Secondary text (slate-400) |
| `--green` | `#22c55e` | Opening nodes, success |
| `--blue` | `#3b82f6` | Decision nodes, primary accent |
| `--amber` | `#f59e0b` | Ending nodes, warnings |
| `--red` | `#ef4444` | Abrupt end nodes, errors |

### Node Type → Visual Encoding

| Node Type | Shape | Background | Border | Text Color | Cytoscape Selector |
|-----------|-------|-----------|--------|------------|-------------------|
| opening | round-rectangle | `#052e16` | `#22c55e` (green) | `#4ade80` | `node[type="opening"]` |
| decision | round-rectangle | `#1e3a5f` | `#3b82f6` (blue) | `#60a5fa` | `node[type="decision"]` |
| emotion | ellipse | `#2e1065` | `#a78bfa` (purple) | `#c4b5fd` | `node[type="emotion"]` |
| action | diamond | `#422006` | `#f59e0b` (amber) | `#fbbf24` | `node[type="action"]` |
| ending | ellipse | `#422006` | `#f59e0b` (amber) | `#fbbf24` | `node[type="ending"]` |
| abrupt | triangle | `#450a0a` | `#ef4444` (red) | `#f87171` | `node[type="abrupt"]` |

### Node Type Inference Logic

```
depth === 0                → opening
state_id === "abrupt_end"  → abrupt
state_id === "normal_end"  → ending
no facts + has emotions    → emotion
branch_key.action exists   → action
otherwise                  → decision
```

## Layout Engine

### Dagre Configuration

- Direction: top-to-bottom (`rankDir: 'TB'`)
- `spacingFactor: 1.2`, `nodeSep: 30`, `rankSep: 120`

### Depth Spacing Override

After dagre layout, `applyDepthSpacing()` enforces custom Y positions:
- Depth 0→1: 3× base separation (give opening room)
- Depth 1→2: 2× base separation
- Depth 2→3: 2× base separation
- Depth 3+: 1× base separation

End nodes (`normal_end`, `abrupt_end`) are positioned below all other nodes at `maxY + 2×sep`, centered horizontally.

`enforceParentAboveChild()` iteratively pushes child Y below parent Y (max 50 iterations).

### Action-Flow Cross Edges

Dashed gray edges connect action nodes to their sibling non-action nodes, showing the collector action → customer response flow within a parent. Leaf action nodes also get implicit edges to the appropriate end node (normal if has closing action, abrupt otherwise).

## Dialog Tracer

### Panel Layout

Right sidebar (420px) with two sub-panels:
1. **Flow Panel** (flex: 1) — dialog selector + animated turn-by-turn flow
2. **Info Panel** (max 40%, slides open) — selected node details

### Tracing Algorithm (`traceDialogPath`)

Walks the tree following each turn's state:
1. Start at root (initial_contact)
2. For each customer turn:
   - Navigate to child matching each fact (skip inherited facts)
   - Navigate to child matching each emotion
   - Fall back to fact+emotion combo, then to current node's children
3. For each collector turn:
   - Navigate to child matching the action
4. End at `normal_end` (if has closing) or `abrupt_end`

Returns: ordered list of node IDs forming the path through the tree.

### Playback Controls

- **Start** — auto-advances through turns at 1400ms intervals; button becomes "Pause" with pulse animation
- **End** — jumps to last turn; button label toggles "End" / "Abrupt End" based on closing detection
- **View** — toggles between full tree view and linear dialog-path-only view

### Path Highlighting

- On-path nodes/edges: full opacity, blue highlight
- Off-path nodes/edges: 0.2 / 0.1 opacity
- Active turn node: white border, centered in viewport

## Node Info Panel

Slides open when a node is tapped. Shows:
- **Type** — human-readable node type label
- **Branch Key** — facts (green tags) and emotions (purple tags)
- **Inherited Facts** — facts propagated from parent chain
- **Sentences** (up to 10) — each showing:
  - Collector action tag (amber)
  - Customer willingness tag (blue)
  - Fact context tags (green)
  - Script text
  - Score bars: HWR (green ≥60%, amber 40-60%, red <40%), SAS, bitmask (binary)

## View Mode (Dialog Path Linearization)

When "View" is toggled on, the graph rebuilds showing only the traced path as a linear sequence:
- Nodes positioned in a vertical column (320px apart)
- Back-edges (when path revisits a node) rendered as dashed gray lines
- Back-edge source nodes offset to the right to avoid overlap
- `cy.fit(undefined, 80)` for padding

## Modifying the UI

When changing the tree explorer:

1. **Adding node types**: Add a Cytoscape style entry in `CY_STYLE` array, add a legend item in the toolbar HTML, and update `nodeType()` function
2. **Changing colors**: Update both CSS custom properties (for HTML elements) and Cytoscape style entries (for graph nodes)
3. **Adding score fields**: Add rendering in `showNodeInfo()` sentence loop, following the `score-row` / `sbar` pattern
4. **Changing layout**: Adjust `applyDepthSpacing()` multipliers or dagre config; run `enforceParentAboveChild()` after any Y changes
5. **Adding tracer features**: Add to `traceDialogPath()` for navigation logic, `renderFlow()` for display, and `activateStep()` for playback

All JS is inline in the HTML file. No build step. The three `.min.js` libraries are bundled for offline operation.
