# Tree Check Script — Implementation Plan

**Created:** 2026-07-07
**Purpose:** A standalone script that loads the generated `decision_tree.json` (and optionally `decision_tree_scored.json`) and validates every structural, semantic, and scoring invariant derived from F004/F005 design docs, ADRs, and the SCBGE guideline. Runs as a CI gate and ad-hoc diagnostic.

---

## 1. Design Principles

- **Standalone**: no test framework dependency; runnable as `python3 -m f004_decision_tree.check_tree`
- **Structured output**: JSON report with `{pass, fail, warn, checks: [...]}` for each invariant
- **Exit code**: 0 = all hard checks pass; 1 = any hard check fails
- **Two modes**: `--tree` (F004 only, fast), `--scored` (F004+F005, requires scored JSON)
- **No side effects**: read-only; never modifies the tree
- **Deterministic**: same tree → same report, every time

## 2. Invariant Categories & Check Count

| Category | Hard | Soft | Checks |
|----------|------|------|--------|
| Structure (S) | 13 | 5 | 18 |
| Node (N) | 21 | 1 | 22 |
| Sentence (SE) | 15 | 1 | 16 |
| Gesture (G) | 10 | 1 | 11 |
| Coverage (C) | 5 | 4 | 9 |
| Scoring (SC) | 24 | 4 | 28 |
| Branching (B) | 12 | 1 | 13 |
| Additive (A) | 7 | 0 | 7 |
| Output (O) | 7 | 1 | 8 |
| **Total actionable** | **114** | **18** | **132** |

(Visualization V and Merge Collector M are runtime/UX concerns, not artifact-invariant — excluded from the check script.)

## 3. Script Structure

```
src/f004_decision_tree/check_tree.py

def check_tree(tree, records=None, scored=False) -> Report
    # Top-level: runs all check groups, returns Report

class Report:
    checks: list[CheckResult]
    def summary() -> str
    def exit_code() -> int

class CheckResult:
    id: str          # e.g. "S1", "N4", "SC8"
    category: str    # "structure", "node", ...
    severity: str    # "hard" | "soft"
    status: str      # "pass" | "fail" | "warn" | "skip"
    message: str     # human-readable
    details: list    # offending items (node ids, sentence ids, etc.)

# Check groups (one function per category):
def _check_structure(tree) -> list[CheckResult]
def _check_nodes(tree) -> list[CheckResult]
def _check_sentences(tree) -> list[CheckResult]
def _check_gestures(tree, records) -> list[CheckResult]
def _check_coverage(tree, records) -> list[CheckResult]
def _check_scoring(tree) -> list[CheckResult]       # only if scored
def _check_branching(tree) -> list[CheckResult]
def _check_additive(tree) -> list[CheckResult]
def _check_output(tree, scored_tree) -> list[CheckResult]
```

## 4. Check Implementations (by category)

### 4.1 Structure (S1–S18)

| ID | Check | Implementation |
|----|-------|---------------|
| S1 | root state_id == "initial_contact" | `tree["state_id"]` |
| S2 | root role == "opening" | `tree.get("role")` |
| S3 | exactly 1 normal_end as root child | count children with state_id |
| S4 | exactly 1 abrupt_end as root child | count children with state_id |
| S5 | end nodes are direct children of root | check parent |
| S6 | end nodes role == "ending" | check role field |
| S7 | 3 structural anchors exist | S2 ∧ S3 ∧ S4 |
| S8 | every leaf is end node or has ending gesture | walk leaves |
| S9 | every path terminates at end node | walk all root→leaf paths |
| S10 | tree is DAG (no cycles) | DFS with visited tracking |
| S11 | no cycles via _is_ancestor | same as S10 |
| S12 | (runtime concern — skip) | skip |
| S13 | DAG nodes share by node_id | collect node_ids, check duplicates are intentional |
| S14 | single-child ratio < 85% | count single-child nodes / total |
| S15 | max depth (soft, report only) | BFS depth |
| S16 | node count (soft) | count |
| S17 | DAG shared node count (soft) | count nodes with >1 parent |
| S18 | (visual — skip) | skip |

### 4.2 Node (N1–N22)

| ID | Check | Implementation |
|----|-------|---------------|
| N1 | every non-end node has node_id | walk, check field |
| N2 | every non-end node has inherited_facts | walk, check field |
| N3 | every non-end node has inherited_emotions | walk, check field |
| N4 | every node role ∈ {opening, ending, decision, action} | walk, check |
| N5 | root role == "opening" | (covered by S2) |
| N6 | end nodes role == "ending" | (covered by S6) |
| N7 | fact/emotion children role == "decision" | check children of decision nodes |
| N8 | action children role == "action" | check a:xxx children |
| N9 | no composite branch keys (facts+emotions) | check each node's bk |
| N10 | no multi-fact branch keys (len(facts)>1) | check each node's bk |
| N11 | branch_key has exactly 1 top-level key | check dict keys |
| N12 | no duplicate sibling nodes by identity | per-parent sibling check |
| N13 | (same as N12) | |
| N14 | inherited_facts excludes own branch_key.facts | check per node |
| N15 | inherited_emotions excludes own branch_key.emotions | check per node |
| N16 | no redundant fact nodes (own fact in inherited) | check per node |
| N17 | no redundant emotion nodes (own emotion in inherited) | check per node |
| N18 | keywords sorted in branch_key | check sorted() |
| N19 | action nodes use bk={"action":...} and state_id="a:..." | check pattern |
| N20 | end nodes use bk={"end_type":...} | check pattern |
| N21 | (runtime — skip) | |
| N22 | (runtime — skip) | |

### 4.3 Sentence (SE1–SE16)

| ID | Check | Implementation |
|----|-------|---------------|
| SE1–SE4 | required fields: script_text, script_id, source_call_ids, customer_willingness | walk all sentences |
| SE5 | collector_action present when action label exists | check action nodes |
| SE6 | fact_context present | walk all sentences |
| SE7 | sentences with collector_action live under action child nodes | check placement |
| SE8 | sentences without collector_action in parent pool | check placement |
| SE9 | state=None turns have no collector_action key | check |
| SE10 | no synthetic "other" action category | check action values |
| SE11 | (covered by SE9) | |
| SE12 | every leaf has non-empty sentence_pool | walk leaves |
| SE13 | no duplicate script_text in any single pool | dedup check per pool |
| SE14 | merged turns ≤ 150 chars | check script_text length |
| SE15–SE16 | (runtime — skip) | |

### 4.4 NEW: Per-Dialog Invariants (user's specific requests)

| ID | Check | Implementation |
|----|-------|---------------|
| D1 | **No duplicate facts in a single dialog path** — within one call_id's traversal, no fact appears twice as a branch key | trace each call_id's path through the tree; collect facts from branch_keys; check for duplicates |
| D2 | **No duplicate emotions in a single dialog path** — same for emotions | trace each call_id's path; check |
| D3 | **Every dialog reaches an end node** — each call_id's sentences appear in a path that terminates at normal_end or abrupt_end | for each call_id, find the deepest node containing its sentences; check path reaches end |
| D4 | **No duplicate script_id** — script_id (= call_id + turn_number) is globally unique | collect all script_ids; check set size == list size |
| D5 | **No duplicate nodes by identity** — no two nodes share the same (inherited_facts, inherited_emotions, branch_key) unless they are the same object (DAG share) | build identity map; flag true duplicates (different objects, same identity) |

### 4.5 Gesture (G1–G11)

| ID | Check | Implementation |
|----|-------|---------------|
| G1 | root pool has opening gesture sentences | check root pool |
| G2 | root has no a:greeting child | check children |
| G3 | all records with greetings represented in root | (needs records) |
| G4 | ending sentences have gesture_type="ending" | walk normal_end pool |
| G5 | normal_end holds ending sentences | check |
| G6 | no ending sentences outside end nodes | walk all pools |
| G7 | dialogs without closing → abrupt_end | (needs records) |
| G8 | multiple greetings per record captured | (needs records) |
| G9 | greetings in root at insert (structural) | check root pool only |
| G10 | closings in normal_end at insert | check normal_end pool only |
| G11 | (runtime — skip) | |

### 4.6 Coverage (C1–C9)

| ID | Check | Implementation |
|----|-------|---------------|
| C1 | all call_ids from data in tree | (needs records) |
| C2 | all facts from data in tree (branch_key or inherited) | (needs records) |
| C3 | all emotions from data in tree | (needs records) |
| C4 | empty-pool branch nodes allowed | (informational) |
| C5 | (runtime — skip) | |
| C6 | all conversations in scored tree | (needs scored) |
| C7–C9 | action/fact/emotion counts (soft) | count |

### 4.7 Scoring (SC1–SC28) — only with `--scored`

| ID | Check | Implementation |
|----|-------|---------------|
| SC1 | bg_constraints has exactly 10 keys | walk sentences |
| SC2 | bg_bitmask has exactly 10 keys | walk sentences |
| SC3 | bg_bitmask_int ∈ [0, 1023] | walk sentences |
| SC4 | bg_bitmask_int correctly encodes the 10 fields | recompute and compare |
| SC5 | bitmask AND filtering correctness | sample check |
| SC6 | intersection merge for multi-source | check multi-source sentences |
| SC7 | win_rate ∈ [0, 1] | walk sentences |
| SC8 | win_rate == weight*sentence_hwr + (1-weight)*node_hwr | recompute and compare |
| SC9 | win_rate_node ∈ [0, 1] | walk sentences |
| SC10 | win_rate_node exists | walk sentences |
| SC11–SC14 | (formula checks — covered by SC8) | |
| SC15 | sas ∈ [0, 1] | walk sentences |
| SC16–SC18 | (runtime computation — skip) | |
| SC19 | uplift_score == 0 | walk sentences |
| SC20 | csi == 0 | walk sentences |
| SC21 | deferred == True | walk sentences |
| SC22 | embedding absent from JSON | walk sentences |
| SC23 | conversation_context present | walk sentences |
| SC24 | (DB-only — skip in JSON mode) | |
| SC25 | bg_background present with 12 fields | walk sentences |
| SC26 | numeric fields not in bitmask | check bg_constraints keys |
| SC27 | (covered by SC4+SC5) | |
| SC28 | (runtime — skip) | |

### 4.8 Branching (B1–B13)

| ID | Check | Implementation |
|----|-------|---------------|
| B1 | branches keyed by (facts, emotions) only — no willingness in branch_key | check all branch_keys |
| B2 | new decision point only for new facts/emotions | (structural — covered by N9/N10) |
| B3 | willingness-only changes don't create branches | (covered by B1) |
| B4 | (covered by B1) | |
| B5 | (runtime — skip) | |
| B6 | (runtime — skip) | |
| B7 | fact-by-fact walking → single-key nodes | (covered by N9/N10) |
| B8 | (runtime — skip) | |
| B9 | (informational) | |
| B10 | action split scoped to decision nodes only | check action nodes are children of decision nodes |
| B11 | redundant-fact skip (no own fact in inherited) | (covered by N16) |
| B12 | redundant emotion collapse | (covered by N17) |
| B13 | (runtime — skip) | |

### 4.9 Additive (A1–A8)

| ID | Check | Implementation |
|----|-------|---------------|
| A1 | tree built via additive inserter (no composite nodes) | (covered by N9) |
| A2 | no global transform artifacts (no composite bk, no multi-fact bk) | (covered by N9/N10) |
| A3 | merge_dialogs produces valid tree | (covered by all structure checks) |
| A4 | idempotency — same call_id twice doesn't duplicate | check no duplicate script_ids per call_id |
| A5 | dedup applied | (covered by N12) |
| A6 | (runtime — skip) | |
| A7 | base structure exists | (covered by S1–S6) |
| A8 | (runtime — skip) | |

### 4.10 Output (O1–O8)

| ID | Check | Implementation |
|----|-------|---------------|
| O1 | decision_tree.json exists and is valid JSON | try load |
| O2 | decision_tree_scored.json exists (if --scored) | try load |
| O3 | scored tree structure matches un-scored (same nodes/edges) | compare node counts, state_ids |
| O4 | scored fields present on every sentence | walk and check |
| O5–O8 | (DB-only — skip in JSON mode) | |

## 5. Per-Dialog Path Tracing (for D1–D3)

The per-dialog checks (D1, D2, D3) require tracing each call_id's path through the tree:

```python
def trace_call_id(tree, call_id):
    """Walk the tree and find the path of nodes containing sentences from this call_id."""
    path = []
    def walk(node):
        has_cid = any(call_id in s.get("source_call_ids", []) for s in node.get("sentence_pool", []))
        if has_cid:
            path.append(node)
        for child in node.get("children", []):
            walk(child)
    walk(tree)
    return path
```

For D1/D2: collect `branch_key.facts` and `branch_key.emotions` from the path nodes; check for duplicates.

For D3: check that the last node in the path is or reaches an end node.

## 6. CLI Interface

```bash
# F004 checks only (fast, ~1s)
python3 -m f004_decision_tree.check_tree

# F004 + F005 checks (requires scored JSON)
python3 -m f004_decision_tree.check_tree --scored

# JSON report to stdout
python3 -m f004_decision_tree.check_tree --scored --json

# Check specific invariants only
python3 -m f004_decision_tree.check_tree --only S1,S2,N4,D1

# Verbose: show passing checks too
python3 -m f004_decision_tree.check_tree -v
```

## 7. File Layout

```
src/f004_decision_tree/check_tree.py    # the script
src/tests/f004_decision_tree/test_check_tree.py  # unit tests for the checker itself
```

## 8. Execution Order

1. Write `check_tree.py` with all check functions
2. Write `test_check_tree.py` with smoke tests (known-good tree passes, known-bad tree fails specific checks)
3. Run against current `decision_tree.json` — expect all pass
4. Run against current `decision_tree_scored.json` — expect all pass
5. Intentionally corrupt tree, verify specific checks catch the corruption
