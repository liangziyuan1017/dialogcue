---
id: ADR-014
title: Bundled JS Libraries for Offline Operation
status: accepted
created: 2026-06-16
updated: 2026-06-16
decision_type: design
feature_ids: [F004]
---

# ADR-014: Bundled JS Libraries for Offline Operation

## Context

The tree explorer originally loaded Cytoscape.js, dagre, and cytoscape-dagre from CDN. This required internet access to view the tree, which is problematic for:
- Offline demo environments
- Internal network deployments at the bank
- Reproducible builds without external dependency

## Decision

Bundle the three JS libraries locally in `src/f004_decision_tree/ui/`:
- `cytoscape.min.js` (~1.1MB)
- `dagre.min.js` (~350KB)
- `cytoscape-dagre.min.js` (~15KB)

Update `tree_explorer.html` to reference local `<script>` tags instead of CDN URLs.

## Why

- Offline operation is a hard requirement for bank internal deployments
- No runtime dependency on external CDN availability
- Reproducible — same files always produce same result
- The libraries are stable (Cytoscape.js v3.x, dagre v0.8.x) — no need for frequent updates

## Consequences

- `src/f004_decision_tree/ui/` directory has 3 additional large JS files (~1.5MB total)
- Library updates require manual download and replacement
- No CDN caching benefit — but for a single-page tool this is negligible
