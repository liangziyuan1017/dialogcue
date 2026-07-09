---
id: F004b
name: Decision Tree Invariant Checker
status: merged
owner: agent
source: tree-check-script-plan.md
created: 2026-07-07
updated: 2026-07-09
merged: 2026-07-09
depends_on: [F004, F005]
---

# F004b: Decision Tree Invariant Checker

## Why

The decision tree is the core artifact consumed by the retrieval engine (F006) and the API (F014). Any structural corruption — duplicate nodes, missing fields, broken termination, stale scoring — silently degrades retrieval quality. A deterministic checker validates every invariant derived from F004/F005 design docs, ADRs, and the SCBGE guideline. It runs as a CI gate and ad-hoc diagnostic.

## What

A standalone script (`check_tree.py`) that loads `decision_tree.json` (and optionally `decision_tree_scored.json`) and validates 132 actionable invariants across 10 categories. Outputs a structured JSON report with pass/fail/warn/skip per check.

### Design Principles

- **Standalone**: no test framework dependency; runnable as `python3 -m f004_decision_tree.check_tree`
- **Structured output**: JSON report with `{pass, fail, warn, checks: [...]}` for each invariant
- **Exit code**: 0 = all hard checks pass; 1 = any hard check fails
- **Two modes**: `--tree` (F004 only, fast), `--scored` (F004+F005, requires scored JSON)
- **No side effects**: read-only; never modifies the tree
- **Deterministic**: same tree → same report, every time

### Invariant Categories

| Category | ID prefix | Hard | Soft | Total |
|----------|-----------|------|------|-------|
| Structure | S | 13 | 5 | 18 |
| Node | N | 21 | 1 | 22 |
| Sentence | SE | 15 | 1 | 16 |
| Termination | T | 5 | 0 | 5 |
| Gesture | G | 10 | 1 | 11 |
| Coverage | C | 5 | 4 | 9 |
| Scoring | SC | 24 | 4 | 28 |
| Branching | B | 12 | 1 | 13 |
| Additive | A | 7 | 0 | 7 |
| Output | O | 7 | 1 | 8 |
| Per-Dialog | D | 0 | 5 | 5 |
| **Total** | | **114** | **23** | **137** |

## Passing Criteria

- All hard checks pass (status=pass)
- No cycles in tree
- All paths terminate at end nodes
- All required fields present on every node and sentence
- Scoring invariants hold when `--scored` is used:
  - `bg_constraints` has exactly 10 bitmask keys
  - `bg_bitmask_int` ∈ [0, 1023]
  - `bg_bitmask_int` correctly encodes the 10 boolean fields
  - `win_rate` ∈ [0, 1], `win_rate_node` ∈ [0, 1]
  - `sas` ∈ [0, 1]
  - `bg_background` is a dict with digit-count/int/passthrough fields
  - No `embedding` field in JSON (DB-only per guideline)

## Acceptance Criteria

- [ ] `python3 -m f004_decision_tree.check_tree` exits 0 on current tree
- [ ] `python3 -m f004_decision_tree.check_tree --scored` exits 0 on current scored tree
- [ ] JSON report has `{pass, fail, warn, checks: [...]}` structure
- [ ] Intentional corruption detected by specific checks
- [ ] `--only S1,N4,D1` runs only the specified checks
- [ ] `--no-records` skips coverage/gesture checks that need source data

## Architecture

```
src/f004_decision_tree/check_tree.py          # CLI entrypoint (thin wrapper)
src/tests/f004_decision_tree/tree_checks/     # check implementation modules
    common.py          # Report, CheckResult, walkers, helpers
    check_structure.py # S1–S18
    check_nodes.py     # N1–N22
    check_sentences.py # SE1–SE16, T1–T5
    check_gestures.py  # G1–G11, C1–C9
    check_scoring.py   # SC1–SC28
    check_branching.py # B1–B13, A1–A8
    check_output.py    # O1–O8, D1–D5
```

The CLI `check_tree.py` is a thin wrapper that imports from `tree_checks/` and handles argument parsing, file loading, and output formatting. All check logic lives in the `tree_checks/` modules.

### Report Structure

```python
class CheckResult:
    id: str          # e.g. "S1", "N4", "SC8"
    category: str    # "structure", "node", "sentence", ...
    severity: str    # "hard" | "soft"
    status: str      # "pass" | "fail" | "warn" | "skip"
    message: str     # human-readable
    details: list    # offending items (node ids, sentence ids, etc.)

class Report:
    checks: list[CheckResult]
    def summary() -> str    # "pass=X fail=Y warn=Z skip=W total=N"
    def exit_code() -> int  # 1 if any hard fail, else 0
    def to_dict() -> dict   # JSON-serializable
```

### Per-Dialog Path Tracing

Checks D1–D3 trace each `call_id`'s path through the tree:

```python
def trace_call_id(tree, call_id):
    path = []
    def walk(node):
        has_cid = any(call_id in s.get("source_call_ids", [])
                      for s in node.get("sentence_pool", []))
        if has_cid:
            path.append(node)
        for child in node.get("children", []):
            walk(child)
    walk(tree)
    return path
```

## CLI Interface

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

# Skip record-dependent checks
python3 -m f004_decision_tree.check_tree --no-records
```

## Check Catalog

Full check descriptions with root causes and verification methods are in [`tree_checks/check_tree_items.md`](../../src/tests/f004_decision_tree/tree_checks/check_tree_items.md).

### Key Scoring Checks (SC1–SC28)

| ID | Check | Detail |
|----|-------|--------|
| SC1 | `bg_constraints` has correct keys | Exactly the 10 BITMASK_FIELDS keys |
| SC2 | `bg_bitmask` has correct keys | Same 10 keys |
| SC3 | `bg_bitmask_int` ∈ [0, 1023] | 10-bit range |
| SC4 | `bg_bitmask_int` matches encoding | Recompute and compare |
| SC7 | `win_rate` ∈ [0, 1] | Blended HWR |
| SC8 | `win_rate` matches blend formula | `weight*sentence_hwr + (1-weight)*node_hwr` |
| SC15 | `sas` ∈ [0, 1] | TF-IDF cosine |
| SC22 | No `embedding` in JSON | DB-only per guideline |
| SC23 | `conversation_context` present | For vector similarity |
| SC25 | `bg_background` is a dict | Digit-count/int/passthrough fields |

### Key Per-Dialog Checks (D1–D5)

| ID | Check | Detail |
|----|-------|--------|
| D1 | No duplicate facts in a dialog path | Trace call_id path; check branch_key facts |
| D2 | No duplicate emotions in a dialog path | Same for emotions |
| D3 | Every dialog reaches an end node | Path terminates at normal_end or abrupt_end |
| D4 | No duplicate script_ids | Globally unique |
| D5 | No duplicate nodes by identity | Same (inherited_facts, inherited_emotions, branch_key) |

## Dependencies

- F004 (Decision Tree Construction) — `decision_tree.json` provides the tree structure
- F005 (Context Tagging & Quality Scoring) — `decision_tree_scored.json` provides scoring fields (when `--scored`)

## Links

- [tree-check-script-plan.md](tree-check-script-plan.md) — Original implementation plan
- [check_tree_items.md](../../src/tests/f004_decision_tree/tree_checks/check_tree_items.md) — Full check catalog with root causes
- [ADR-020](../../decisions/ADR-020-f005-bitmask-scoring-design.md) — Bitmask encoding design
- [ADR-029](../../decisions/ADR-029-additive-tree-building.md) — Additive tree building invariants
- [ADR-030](../../decisions/ADR-030-node-role-tagging.md) — Node role tagging invariants
- [ADR-031](../../decisions/ADR-031-node-hwr-blending.md) — HWR blending formula

## Files

| File | Purpose |
|------|---------|
| `src/f004_decision_tree/check_tree.py` | CLI entrypoint |
| `src/tests/f004_decision_tree/tree_checks/` | Check implementation modules |
| `src/tests/f004_decision_tree/tree_checks/check_tree_items.md` | Full check catalog |
| `src/tests/f004_decision_tree/test_check_tree.py` | Unit tests for the checker |
