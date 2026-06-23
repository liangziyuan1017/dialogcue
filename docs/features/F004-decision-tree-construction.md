---
id: F004
name: Decision Tree Construction
status: complete
owner: agent
source: plan_feature_base.md
created: 2026-06-11
updated: 2026-06-23
depends_on: F003
---

# F004: Decision Tree Construction

## Why

The retrieval engine (F006) needs a traversable decision tree to recommend collector scripts given a customer state. Without the tree, there is no structure to match real-time conversation states against historical successful paths. Additionally, every dialog has an opening gesture and an ending gesture — these must be explicitly represented as start and end nodes in the tree structure.

## What

Build a **collector decision tree** where:
- **Nodes** are decision points keyed by customer response profile `(facts, emotions)`
- **Sentence pools** at each node contain collector scripts, each tagged with `customer_willingness`
- **Willingness** is a label on sentences, NOT a branching factor
- **Branches** diverge only when customer introduces new facts or new emotions
- Fallback via progressive tag removal when exact branch not found
- Output to `/src/decision_tree.json`

### Dialog Gestures (Opening & Ending)

Every dialog has a **start node** and converges to one of two **end nodes**:
- **Start node** (`state_id: "initial_contact"`) — the single root capturing the **opening gesture** (greeting, self-introduction, purpose statement). There is exactly one opening node in the tree.
- **Normal end node** (`state_id: "normal_end"`) — all properly-closed dialogs converge here. Contains all ending gesture sentences (goodbye, confirmation, well-wishes).
- **Abrupt end node** (`state_id: "abrupt_end"`) — all dialogs without proper closings converge here. Contains the abrupt-end marker sentence.
- The tree has exactly **3 terminal-adjacent nodes**: 1 opening (root), 1 normal_end, 1 abrupt_end. Both end nodes are direct children of root.
- Opening and ending gestures are recorded as `gesture_type: "opening"` and `gesture_type: "ending"` on their sentence entries
- The tree is rendered **vertically** (top-to-bottom): opening at top, decision branches in middle, two end nodes at bottom

### Architecture (ADR-011)

Nodes = collector action points. Branches = customer (facts, emotions). Willingness tags each sentence. A new decision point is created ONLY when the customer introduces new facts or new emotions. Willingness-only changes (e.g., conditional → negotiating) do NOT create new branches.

### Current Tree Statistics (2026-06-23)

| Metric | Value |
|--------|-------|
| Total nodes | 309 |
| DAG shared nodes | 9 |
| Max depth | 17 |
| Opening gesture sentences | 217 |
| Ending gesture sentences | 345 |
| Non-gesture sentences | 772 |
| Unique call_ids | 31/31 |
| Branch key actions | 7 (closure, empathy, greeting, information, legal_threat, plan_proposal, pressure) |
| Branch key facts | 53 |
| Branch key emotions | 23 |

### Merge List (7 groups merged from 93 → 64 decision points)

| # | facts | emotions | Willingness levels merged |
|---|-------|----------|--------------------------|
| 1 | ∅ | ∅ | conditional(15) + weak(10) + negotiating(6) + strong(4) |
| 2 | financial_hardship | ∅ | weak(4) + none(4) + negotiating(1) |
| 3 | ∅ | pleading | none(1) + conditional(1) + negotiating(1) |
| 4 | financial_hardship, multiple_debts | ∅ | conditional(1) + weak(1) + none(1) |
| 5 | multiple_debts | ∅ | conditional(1) + none(1) |
| 6 | ∅ | skepticism | negotiating(1) + none(1) |
| 7 | financial_hardship | helplessness | none(1) + resistant(1) |

### Passing Criteria

- Tree has root node with `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`, `customer_willingness`, `collector_action`, `fact_context`
- All 31 conversations represented (every call_id in at least one `source_call_ids`)
- Keywords lexicographically sorted at every node

## Acceptance Criteria

- [x] Root node has `state_id: "initial_contact"`
- [x] Every leaf node has non-empty `sentence_pool`
- [x] Every sentence entry has `script_text`, `script_id`, `source_call_ids`, `customer_willingness`
- [x] All 31 call_ids appear in at least one `source_call_ids`
- [x] Keywords lexicographically sorted at every node
- [x] Branches keyed by (facts, emotions) only — willingness is a sentence label
- [x] Fallback via progressive tag removal works when exact branch not found
- [x] Tree is branching (not chain-like): single-child ratio < 85% (actual: 14.4%)
- [x] Root node sentence_pool entries have `gesture_type: "opening"` for greeting sentences
- [x] Tree has exactly one `normal_end` node and one `abrupt_end` node, both with `gesture_type: "ending"`
- [x] Both end nodes are direct children of root (consolidated endpoints)
- [x] Every dialog path terminates at either `normal_end` or `abrupt_end`
- [x] Ending gesture sentences have `gesture_type: "ending"`
- [x] Dialogs without proper closing are routed to `abrupt_end` node
- [x] No composite branch keys (every node has single fact, single emotion, or single action)
- [x] No redundant fact nodes (own fact never in inherited_facts)
- [x] Sentences with collector_action always under action child nodes for fact/emotion parents
- [x] All facts from data have corresponding nodes in tree
- [x] All emotions from data have corresponding nodes in tree
- [x] Collector turns with no action label captured without `collector_action` key (merged into parent pool)
- [x] Collector turns with `state=None` captured (not silently dropped)
- [x] Customer turns with facts/emotions but no following collector create branch nodes (empty sentence pool)
- [x] Multiple greeting turns per record all captured (no early break)
- [x] No duplicate nodes with same `(inherited_facts, inherited_emotions, branch_key)` identity (sibling dedup)
- [x] Every node has `node_id`, `inherited_facts`, `inherited_emotions`
- [x] No redundant emotion nodes (own emotion never in inherited_emotions)
- [x] DAG shared nodes render as single Cytoscape node with multiple incoming edges
- [x] No cycles in tree structure (cycle prevention in registry reuse)

## Dependencies

- F003 (Reward Labeling) — complete, `output_rewarded.py` exists

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F004 spec
- [ADR-011](../../decisions/ADR-011-decision-tree-approach.md) — Architecture decision
- [ADR-021](../../decisions/ADR-021-node-identity-dedup.md) — Node identity dedup with DAG support
- [ADR-022](../../decisions/ADR-022-redundant-emotion-collapse.md) — Redundant emotion collapse

## Implementation Plan

See [implementation-plan.md](implementation-plan.md)

## Design Decisions

- **Willingness as sentence label, not branch key**: Same (facts, emotions) = same decision point regardless of willingness. Collector sees "under financial_hardship, when customer is weak I say X, when negotiating I say Y" — both under the same branch.
- **Rare facts kept as branches**: Not bucketed into `_other` — data will broaden.
- **Segment-based extraction**: Each conversation is decomposed into segments of (customer branch key → collector sentences), not individual turns. This avoids the chain problem.
- **Fact-by-fact tree walking**: `build_tree` walks each segment's facts and emotions one at a time, creating single-key nodes at each step. Composites are never created, eliminating the need for `_split_composite_nodes` as a non-trivial operation.
- **Local tree building (no global reuse)**: Each segment's branch key is matched only against children of `current_node`, not searched globally. This preserves path continuity — every record's conversation path is a connected subtree.
- **Start/end node model**: The tree has exactly 1 opening node (root) and 2 consolidated end nodes (`normal_end` and `abrupt_end`) as direct children of root. All properly-closed dialogs converge into `normal_end`; all dialogs without proper closings converge into `abrupt_end`. This gives the tree a clean vertical structure: opening at top → decision branches → two end nodes at bottom.
- **Consolidated endpoints**: Rather than scattering many `abrupt_end` leaves throughout the tree, all ending sentences are collected into a single `normal_end` node and all abrupt terminations into a single `abrupt_end` node. This ensures the tree has exactly 2 terminal nodes regardless of data size.
- **Safe terminal stripping**: `_strip_terminal_nodes` only removes `abrupt_end`/`normal_end` nodes during consolidation, not decision nodes that happen to contain ending sentences deep in their subtree. This prevents cascading deletion of valid branches.
- **Cytoscape.js + dagre layout**: Tree is rendered as an interactive graph using Cytoscape.js with the dagre hierarchical layout engine. Supports zoom, pan, drag, click-to-inspect. Nodes are styled by type: rectangles (opening/decision), ellipse (normal end/emotion), diamond (action), triangle (abrupt end). Edges carry branch labels (facts|emotions).
- **collector_action field on sentences**: Each sentence entry carries `collector_action` (e.g. greeting, information, plan_proposal, pressure, empathy, legal_threat, closure) for UI display and filtering. Sentences without an action label are included without this key.
- **Action nodes always created for fact/emotion parents**: `_split_by_action` force-splits sentence pools into action child nodes for any fact or emotion parent, ensuring sentences with `collector_action` always live under `a:xxx` nodes. Sentences without `collector_action` remain in the parent pool. This keeps the tree structure uniform: fact → action → sentences.
- **Redundant fact collapse**: `_collapse_redundant_facts` removes fact nodes whose facts are already in the accumulated parent chain (iterative fixed-point), promoting their sentences and children up. This eliminates duplicate branches where a fact is restated.
- **Strict inherited_facts**: `inherited_facts` contains only facts from the parent chain, never the node's own `branch_key.facts`. This makes the field semantically correct for redundancy detection.
- **Empty-state customer turns**: Customer turns with `facts=[]` and `emotions=[]` don't break segments — collector sentences continue accumulating under the current branch key. This prevents loss of collector turns between customer acknowledgments.
- **state=None handling**: Collector turns with `state=None` (no annotation) are captured without `collector_action` key and merged into the parent node's sentence pool. No synthetic `other` action category is created.
- **No-annotation collector turns**: Collector turns without any action label are included in the tree without `collector_action`, ensuring full coverage of collector speech without inventing labels.
- **Empty-sentence segments**: Customer turns that introduce new facts/emotions but have no following collector sentences still create branch nodes (with empty sentence pools). This ensures all facts and emotions from the data are represented in the tree structure.
- **Multiple greetings per record**: All greeting turns per record are captured (no early `break`), so records with greeting at t0 and another at t2/t3 are fully represented.
- **Dialog tracer with animated walkthrough**: The tree explorer includes a dialog tracer that walks through a selected call record step-by-step, highlighting the corresponding path in the tree. Auto-play animation with flowing node highlights and panel scrolling (1400ms per step).
- **Bundled Cytoscape/dagre JS libraries**: The Cytoscape.js, dagre, and cytoscape-dagre JS libraries are bundled locally in `src/` to avoid CDN dependency and ensure offline operation.
- **Action-to-end edges**: Dashed `action-flow` edges connect action leaf nodes to `normal_end`/`abrupt_end`, ensuring all branches visually connect to an end node in the graph.
- **End node positioning**: End nodes are placed bottom-center of the graph with 2x vertical spacing from the deepest decision layer.
- **Depth spacing**: Each tree depth gets its own Y band based on actual `_depth` (not dagre's rank). Shallow depths (0-2) get 2-3x spacing; depth 3+ gets 1x + 0.5x extra. `enforceParentAboveChild` ensures every child is strictly below its parent.
- **Action node styling**: Action nodes use yellow/amber color with diamond shape. Emotion nodes use purple with ellipse shape. All action categories (including empathy and pressure) render consistently as action type.
- **Edge arrow scale**: Arrows are 1.4x scale on both tree edges and action-flow edges. Action-flow edges use muted slate color (`#475569`) instead of bright teal.
- **Label prefixes stripped**: Node labels strip `a:`, `e:`, `f:` prefixes — the shape already distinguishes node types.
- **View mode renderer**: Dedicated `buildViewGraph` for dialog path view. Walks dialog sequence in order, assigns each node a consecutive row (Y = row × 320). Back edges (return to earlier state) render as dashed slate lines with source offset rightward to avoid crossing. Uses `preset` layout with `cy.fit(undefined, 80)` for comfortable zoom level.
- **No-cache HTTP server**: `serve_tree.py` uses `NoCacheHandler` (Cache-Control: no-store) and `ReusableTCPServer` (allow_reuse_address) for fresh data on every reload.
- **LLM-guided collector turn merging**: Before segment extraction, `_apply_merges()` preprocesses dialogs to merge fragmented collector turns. Two-phase strategy: (1) `_find_merge_candidates()` identifies merge groups using Rule A (consecutive collector), Rule B (ack-only interruption: no facts/emotions, ≤15 words), and Rule C (label-1 turns treated as absent); (2) `_llm_should_merge()` partitions each group into merge subgroups. Same-action consecutive turns auto-merge without LLM. `_ensure_same_action_merged` post-processes LLM results to enforce this. Hard constraint: `MAX_MERGED_WORDS=150` — each merged output ≤150 Chinese characters, enforced by `_enforce_word_limit()` greedy splitting. Cache in `merge_decisions.json` avoids re-calling LLM.
- **Node identity deduplication (ADR-021)**: Nodes are identified by `(inherited_facts, inherited_emotions, branch_key)`. Two nodes with the same identity are the same semantic state. A global `node_registry` in `build_tree()` prevents creating duplicate nodes. Cycle prevention via `_is_ancestor` check. Post-transform `_deduplicate_nodes` catches any remaining sibling duplicates.
- **DAG tree structure**: The tree is a DAG — nodes with the same identity can appear under multiple parents. All recursive walkers use `_visited` sets for cycle protection. The UI uses `node_id` (SHA-256 hash of identity) as the Cytoscape node ID, rendering shared nodes once with multiple incoming edges.
- **Redundant emotion collapse (ADR-022)**: `_collapse_redundant_facts` extended to also collapse emotion nodes whose emotions are already in the accumulated parent emotions (e.g., `anger → anger` → collapse to `anger`). Symmetric with fact collapse. Uses `accumulated_emotions` tracking.
- **Pipeline output filenames**: LLM step output filenames match actual files in `data/`: `output_2.py`, `output_logic.py`, `output_complete.py`, `output_merged.py`.

## Files

| File | Purpose |
|------|---------|
| `src/f004_decision_tree/build_decision_tree.py` | Decision tree construction with registry dedup and cycle prevention |
| `src/f004_decision_tree/tree_transforms.py` | Tree transforms with DAG-safe visited tracking and emotion collapse |
| `src/test_build_decision_tree.py` | Unit tests (613 lines, 34 tests) |
| `src/test_record_coverage.py` | Record-level coverage tests (436 lines, 10 tests) |
| `src/test_ui_rendering.py` | UI rendering type/shape/color/depth tests (396 lines, 20 tests) |
| `src/test_merge_collector.py` | Merge collector tests (41 tests) |
| `src/decision_tree.json` | Generated output (315 nodes, 211 leaves) |
| `src/tree_explorer.html` | Interactive vertical tree visualizer (Cytoscape.js + dagre) with dialog tracer and view mode renderer (853 lines) |
| `src/dialog_records.json` | Dialog records for UI path tracing |
| `src/merge_decisions.json` | Cached LLM merge decisions |
| `src/cytoscape.min.js` | Bundled Cytoscape.js library |
| `src/cytoscape-dagre.min.js` | Bundled Cytoscape-dagre layout plugin |
| `src/dagre.min.js` | Bundled dagre graph layout engine |
