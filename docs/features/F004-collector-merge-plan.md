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
- Text length ≤ 15 characters (after stripping punctuation)
- Not a real reply (no substantive content)

**Rule C — Label-1 turns treated as absent**: Customer turns with `"label": 1` are manually inserted annotations. They are skipped during candidate identification — consecutive collector turns separated only by label-1 turns are treated as if the label-1 turns don't exist. These turns are removed from the output after merging.

**Same-action auto-merge**: If all turns in a candidate group share the same `collector_action`, they are automatically merged (no LLM call needed). After LLM partitioning, `_ensure_same_action_merged` post-processes the REMOVED_FIELD_result to merge any consecutive same-action turns that the LLM kept separate.

These rules produce **merge groups** — sequences of collector turns that should potentially be merged.

### Phase 2: LLM merge decision (grouping with word limit)

For each merge group, ask DeepSeek how to **partition** the collector turns into merge subgroups. The LLM sees:
- The full text of each collector turn in the group (with word count)
- The customer interruption text (if any)
- The surrounding context (previous and next turns)

LLM prompt asks for a **grouping**: a partition of the turns into subgroups. Turns in the same subgroup are merged; single-element subgroups are kept intact.

**Hard constraint: each merged output ≤ 100 words.** If a subgroup's combined text exceeds 100 words, the code automatically splits it greedily (accumulate until limit, then start a new subgroup). The 100-word limit is chosen for real-time recommendation serving: ~30s of speech, scannable in 2-3 seconds, and accommodates the natural length of single turns in the data (up to ~119 words).

Example: 4 sentences of 45, 50, 90, 30 words → LLM proposes `[[0,1],[2],[3]]` → merge 45+50=95 (≤100), keep 90 and 30 intact.

**Why LLM for Phase 2**: Rule-based heuristics can identify candidates but cannot reliably distinguish:
- "t10: plan proposal + t12: plan proposal continuing same plan" → MERGE
- "t6: plan proposal + t8: different plan proposal after customer objection" → KEEP

The LLM understands discourse coherence — whether turns are continuing the same argument/proposal or starting a new one. The word limit is enforced in code as a safety net even if the LLM misjudges length.

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
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Create: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_find_merge_candidates(turns)` returns correct groups for dialog 2
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_find_merge_candidates()` applies Rule A (consecutive collector) and Rule B (ack-only interruption) to produce merge groups
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: LLM merge decision

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_llm_should_merge(group, context)` returns groups `[[0,1],[2]]` with mocked LLM response; test word-count enforcement splits groups exceeding 100 words; test same-action auto-merge; test `_ensure_same_action_merged` post-processing
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_llm_should_merge()` builds prompt, calls DeepSeek via `llm_client.py`, parses groups response; same-action groups auto-merge without LLM; `_ensure_same_action_merged` post-processes LLM results; enforces `MAX_MERGED_WORDS=100` by greedily splitting oversized groups
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Turn merging

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`
- Modify: `src/test_merge_collector.py`

**Step 1: Write failing test** — test `_merge_turns(group)` produces correct merged entry with concatenated text, merged script_id, union of source_call_ids, merged_from list
**Step 2: Run test to verify it fails**
**Step 3: Implement** — `_merge_turns()` concatenates texts, creates merged entry
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 4: Integrate into build pipeline

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`

**Step 1: Implement** — Add `_merge_collector_turns()` as preprocessing step in `build_tree()` before `_extract_segments()`. The merged turns replace the original turns in the dialog before segment extraction.
**Step 2: Verify** — existing tests still pass (tree structure preserved)
**Step 3: Commit**

### Task 5: LLM merge cache

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py`

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
将这些催收员连续话语分组。同一组的会合并为一个句子，不同组保留独立。

约束：每个合并组的总字数不能超过100字。

催收员话语:
  [0] (45字) 催收员: {turn_0_text}
  [客户说: "{customer_text}"]
  [1] (50字) 催收员: {turn_1_text}
  [2] (90字) 催收员: {turn_2_text}
  [3] (30字) 催收员: {turn_3_text}

分组规则 (偏向不合并，只有明确是同一话题才合并):
- 同一方案解释的连续话语 → 合并（如果总字数≤100）
- 客户只是简短应答(嗯/好)后催收员继续同一方案 → 合并
- 不同论点/话题 → 分开
- 客户提出新观点/异议 → 分开
- 不确定 → 分开

回复JSON:
{"groups": [[0,1],[2],[3]], "reason": "简要说明"}
groups是索引列表，每个子列表是一个合并组。单独的话语用单元素列表如[2]。
```

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Total sentences | 1334 | 868 |
| Tree nodes | 333 | 315 |
| Merged >100 words | N/A | 0 |
| Original >100 words | 1 | 1 |
| Fragmented plan proposals | ~30 | ~0 |
| HWR accuracy | diluted across fragments | per complete utterance |
| SAS reliability | low for short fragments | higher for complete utterances |

## Implementation Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_MERGED_WORDS` | 100 | Max Chinese chars per merged output |
| `ACK_MAX_WORDS` | 15 | Max customer turn words to treat as ack interruption |
