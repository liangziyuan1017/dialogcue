# F004 Fix: Collector Turn Merge — Implementation Plan

**Problem**: Collector turns are fragmented when customer interrupts with acknowledgments (嗯/好/对) or when collector speaks consecutive turns. This produces incomplete sentence recommendations.

**Goal**: Merge fragmented collector turns into complete logical utterances before tree building. Acknowledgment detection uses both keyword list AND state annotations (no facts/emotions/willingness = ack). Acknowledgment text is discarded completely.

**Architecture**: Add `_merge_collector_fragments(turns)` preprocessing step in `build_decision_tree.py` that runs before `_extract_segments()`. Produces a cleaned turn list where each collector entry is a complete utterance. Merged turns carry `merged_from` metadata for dialog tracer traceability.

**Tech Stack:** Python, pytest

---

### Task 1: Implement `_is_acknowledgment(turn)` detector

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that turns with short keyword (嗯/好/对) AND no state annotations are acknowledgments; test that turns with facts/emotions/willingness are NOT acknowledgments; test that longer text is NOT acknowledgment even with no state
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_is_acknowledgment(turn)`: keyword list (嗯/好/对/是/哦/噢/啊/喂/嗯嗯/好好/对对/是的/明白/知道/了解) AND len(text) ≤ 6 AND state has no facts/emotions/willingness. Also true if no state at all and text matches keyword + length.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Implement `_merge_collector_fragments(turns)` merger

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that consecutive collector turns are merged (texts concatenated, source_turn_indices unioned); test that collector-ack-collector is merged (ack discarded); test that collector-real_reply-collector is NOT merged; test that greeting turns are NOT merged with subsequent turns
**Step 2: Run test to verify it fails**
**Step 3: Implement** — Walk turns, buffer collector turns. When customer turn is acknowledgment, discard it and continue buffering. When customer turn is real reply, flush buffer as merged collector turn, then emit customer turn. Merged turn gets `merged_from: [turn_index_list]` for tracer.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Integrate merge into `build_tree()` and `_extract_segments()`

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Write failing test** — test that `build_tree()` with fragmented records produces tree with merged sentences (longer script_text, merged source_call_ids)
**Step 2: Run test to verify it fails**
**Step 3: Implement** — Call `_merge_collector_fragments(turns)` at the start of `build_tree()` before greeting extraction and segment extraction. Also apply before greeting extraction. Merged turns get `script_id` based on first turn index with `_merged` suffix if multiple turns merged.
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Update `dialog_records.json` generation for tracer

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/tree_explorer.html`

**Step 1: Implement** — `write_dialog_records()` now outputs merged turns. Each merged turn has `merged_from: [indices]` so the tracer can highlight the correct range. The `renderFlow()` function in tree_explorer.html shows merged turns as a single step with a "merged" badge when `merged_from` has multiple indices. Clicking a merged step highlights the full original turn range.
**Step 2: Verify** — open in browser, select a dialog with known fragmentation (2320348750405373371), confirm merged turns display correctly
**Step 3: Commit**

### Task 5: Move old files, regenerate, validate

**Files:**
- Create: `src/old_tree/decision_tree.json`
- Create: `src/old_tree/decision_tree_scored.json`
- Create: `src/old_tree/dialog_records.json`
- Modify: `src/decision_tree.json`
- Modify: `src/decision_tree_scored.json`
- Modify: `src/dialog_records.json`

**Step 1: Copy** current decision_tree.json, decision_tree_scored.json, dialog_records.json to `src/old_tree/`
**Step 2: Regenerate** — run `build_decision_tree.py` to produce new tree, run `score_tree.py` to produce new scored tree, regenerate `dialog_records.json`
**Step 3: Validate** — all existing tests pass, tree has fewer sentence entries (fragments merged), all 31 call_ids still represented, dialog tracer works with merged turns
**Step 4: Commit**

### Task 6: Update tests for new tree structure

**Files:**
- Modify: `src/test_build_decision_tree.py`
- Modify: `src/test_record_coverage.py`
- Modify: `src/test_score_tree_integration.py`

**Step 1: Update** expected node/sentence counts for merged tree
**Step 2: Add tests** — test that no fragmented sentences remain (no sentence under 5 chars that is clearly a fragment), test that merged sentences contain concatenated text from original turns
**Step 3: Run all tests**
**Step 4: Commit**
