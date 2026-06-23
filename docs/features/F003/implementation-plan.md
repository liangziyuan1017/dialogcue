# F003: Reward Labeling — Implementation Plan

**Feature:** F003 — `docs/features/F003/reward-labeling.md`
**Goal:** Determine R ∈ {0, 1} per conversation via LLM detection of repayment commitment triggers, counterfactual verification, and cross-validation against plan_evaluation.
**Acceptance Criteria:**
- All 31 records have `reward` ∈ {0, 1}
- Every R=1 record has `reward_evidence` with `trigger_text` and `trigger_turn_index`
- Every R=1 record has `reward_action_credit` with turn details
- R=1 records consistent with `plan_evaluation`
- No R=0 record has `reward_action_credit`
**Architecture:** LLM scans final turns for commitment triggers (agree_to_pay, promise_to_pay). Counterfactual step credits the preceding collector turn. Cross-validation compares R against plan_evaluation to flag mismatches as warnings.
**Tech Stack:** Python, DeepSeek LLM (via existing API), pytest

---

### Task 1: Reward Detection Logic

**Files:**
- Create: `src/f003_reward_labeling/reward_label.py`
- Test: `src/test_reward_label.py`

**Step 1: Write failing test** — test that `label_reward(record)` returns dict with `reward` ∈ {0,1}, and R=1 records have `reward_evidence` + `reward_action_credit`
**Step 2: Run test to verify it fails**
**Step 3: Implement `label_reward()`** — LLM call to detect commitment triggers in final turns, counterfactual credit assignment
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 2: Cross-Validation

**Files:**
- Modify: `src/f003_reward_labeling/reward_label.py`
- Modify: `src/test_reward_label.py`

**Step 1: Write failing test** — test that `cross_validate(results)` flags R=1/plan_evaluation mismatches as warnings
**Step 2: Run test to verify it fails**
**Step 3: Implement `cross_validate()`** — compare reward against plan_evaluation, emit warnings
**Step 4: Run test to verify it passes**
**Step 5: Commit**

### Task 3: Batch Processing & Output

**Files:**
- Modify: `src/f003_reward_labeling/reward_label.py`
- Create: `src/f003_reward_labeling/output_rewarded.py`

**Step 1: Write failing test** — test that `label_all(records)` processes all 31 records and output has correct structure
**Step 2: Run test to verify it fails**
**Step 3: Implement `label_all()`** — iterate records, call `label_reward`, write to `output_rewarded.py`
**Step 4: Run test to verify it passes**
**Step 5: Commit**
