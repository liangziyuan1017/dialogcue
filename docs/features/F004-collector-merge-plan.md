# F004 Fix: LLM-Guided Collector Turn Merging

## Problem

In some dialogs, a collector's logical utterance is fragmented across multiple turns because the customer interrupts with acknowledgments (嗯/好/对) or short filler that conveys no new information. The decision tree stores each fragment as a separate sentence, causing:

1. **Incomplete recommendations** — system suggests "也就是说您还26000多" instead of the complete utterance
2. **HWR diluted** — win rate split across fragments instead of credited to the complete utterance
3. **SAS distorted** — short fragments have unreliable TF-IDF similarity
4. **Tree bloat** — 91 sentences under 10 chars (6.8%) are mostly fragments

## Scope

| Pattern | Count | 
|---------|-------|
| Consecutive collector turns (no customer in between) | 14 instances across 6 records |
| Collector turns separated by ack-only customer turns (no facts/emotions, ≤15 chars) | ~175 instances across all records |

## Approach

Add a **dialog preprocessing step** `_merge_collector_turns(turns, call_id)` that runs **before** `_extract_segments()` in `build_decision_tree.py`. It uses a two-phase strategy:

### Phase 1: Rule-based candidate identification

Identify merge candidates using deterministic rules (no LLM needed):

**Rule A — Consecutive collector turns**: Two or more collector turns with no customer turn in between. Always a candidate.

**Rule B — Ack-only interruption**: A sequence `collector → customer → collector` where the customer turn has:
- No `facts` and no `emotions` in its state annotation
- Text length ≤ 15 characters
- Not a real reply (no substantive content)

These rules produce **merge groups** — sequences of collector turns that should potentially be merged.

### Phase 2: LLM merge decision

For each merge group, ask DeepSeek whether the collector turns should be merged into one logical utterance. The LLM sees:
- The full text of each collector turn in the group
- The customer interruption text (if any)
- The surrounding context (previous and next turns)

LLM prompt asks: "Are these collector turns part of the same logical utterance (same topic/plan/action), or are they separate dialog exchanges? Respond with: MERGE or KEEP, and a reason."

**Why LLM for Phase 2**: Rule-based heuristics can identify candidates but cannot reliably distinguish:
- "t10: plan proposal + t12: plan proposal continuing same plan" → MERGE
- "t6: plan proposal + t8: different plan proposal after customer objection" → KEEP

The LLM understands discourse coherence — whether turns are continuing the same argument/proposal or starting a new one.

### Merge semantics

When turns are merged:
- **script_text**: Concatenate with space separator
- **script_id**: Use first turn's script_id (e.g., `callid_t10`) with `_merged` suffix
- **source_call_ids**: Union of all source call_ids
- **collector_action**: Use the action from the turn with the most specific action label; if different actions, keep the first (primary) action
- **customer_willingness**: Use the willingness from the last turn in the group (most recent)
- **merged_from**: List of original script_ids for traceability

## Examples from Dialog 2 (2320348750405373371)

| Merge Group | Turns | Rationale |
|-------------|-------|-----------|
| 1 | t10 + t12 | Both plan_proposal continuing the same plan explanation; customer t11 is just "这个减免没有必要" (short objection, no new facts) |
| 2 | t14 + t15 | Consecutive collector turns; t14 is plan_proposal and t15 is pressure continuing the same argument about why the plan is better |
| 3 | t23 + t24 + t25 | Three consecutive collector turns; empathy → plan_proposal → pressure all part of same persuasion sequence |
| 4 | t26 + t27 | Consecutive collector turns; both plan_proposal describing the same repayment schedule |
| 5 | t29 + t31 | plan_proposal + information; both explaining the same repayment timeline (t30 customer says "好的") |
| 6 | t35 + t37 | plan_proposal + pressure; both arguing against 个性化分期 and for the current plan (t36 customer says "但是个性化分期…") |
| 7 | t39 + t41 | pressure + pressure; both explaining why 个性化分期 is unavailable and the current plan is better (t40 customer says "那你们就是不给我办") |

## Implementation Tasks

### Task 1: Rule-based candidate identification

**Files:**
- Modify: `src/build_decision_tree.py`
- Create: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_find_merge_candidates(turns)` returns correct groups for dialog 2
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_find_merge_candidates()` applies Rule A (consecutive collector) and Rule B (ack-only interruption) to produce merge groups
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: LLM merge decision

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_llm_should_merge(group, context)` returns MERGE/KEEP with mocked LLM response
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_llm_should_merge()` builds prompt, calls DeepSeek via `llm_client.py`, parses MERGE/KEEP response
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Turn merging

**Files:**
- Modify: `src/build_decision_tree.py`
- Modify: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_merge_turns(group)` produces correct merged entry with concatenated text, merged script_id, union of source_call_ids, merged_from list
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_merge_turns()` concatenates texts, creates merged entry
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Integrate into build pipeline

**Files:**
- Modify: `src/build_decision_tree.py`

**Step 1: Implement** — Add `_merge_collector_turns()` as preprocessing step in `build_tree()` before `_extract_segments()`. The merged turns replace the original turns in the dialog before segment extraction.
**Step 2: Verify** — existing tests still pass (tree structure preserved)
**Step 3: Commit**

### Task 5: LLM merge cache

**Files:**
- Modify: `src/build_decision_tree.py`

**Step 1: Implement** — Cache LLM merge decisions in `src/merge_decisions.json` keyed by (call_id, turn_indices). On subsequent runs, reuse cached decisions instead of calling LLM again. This avoids re-running ~175 LLM calls on every tree rebuild.
**Step 2: Verify** — second run uses cache (no LLM calls)
**Step 3: Commit**

### Task 6: Regenerate tree + validate

**Files:**
- Modify: `src/decision_tree.json`
- Modify: `src/test_build_decision_tree.py`

**Step 1: Run** `build_decision_tree.py` to regenerate tree with merged turns
**Step 2: Verify** — all existing tests pass, tree has fewer sentence entries, no fragments under 10 chars from merged groups
**Step 3: Commit**

### Task 7: Regenerate scored tree

**Files:**
- Modify: `src/decision_tree_scored.json`

**Step 1: Run** `score_tree.py` to regenerate scored tree from new decision_tree.json
**Step 2: Verify** — all score_tree tests pass
**Step 3: Commit**

## LLM Prompt Design

```
You are analyzing a debt collection phone call dialog. Determine whether consecutive collector (催收员) turns should be MERGED into one logical utterance or KEPT as separate turns.

Context: The collector is speaking to a customer. Sometimes the customer interrupts with a short acknowledgment (嗯/好/对) or brief comment, but the collector continues the same point. In other cases, the customer raises a new objection and the collector responds with a different argument.

Collector turns to evaluate:
{turn_1_text}
[Customer said: "{customer_text}"]
{turn_2_text}

Should these be merged into one logical utterance?

Rules:
- MERGE if they are continuing the same argument, proposal, or explanation
- MERGE if the customer interruption is just an acknowledgment and the collector continues the same topic
- KEEP if the collector shifts to a genuinely different topic or action after the customer's response
- KEEP if the customer raised a substantive new point and the collector is responding to that new point

Respond in JSON:
{
  "decision": "MERGE" or "KEEP",
  "reason": "brief explanation"
}
```

## Expected Impact

| Metric | Before | After (estimated) |
|--------|--------|-------------------|
| Total sentences | 1334 | ~1200-1250 |
| Sentences <10 chars | 91 (6.8%) | ~40-50 |
| Fragmented plan proposals | ~30 | ~0 |
| HWR accuracy | diluted across fragments | per complete utterance |
| SAS reliability | low for short fragments | higher for complete utterances |
