# F000: State Keyword Discovery — Implementation Plan

**Feature:** F000 — `docs/features/F000-state-keyword-discovery.md`
**Goal:** Analyze all turns across 31 records to discover fact groups, emotion groups, collector action groups, and data-driven willingness levels from real data. Output taxonomy to `/src/state_keywords.json`.
**Acceptance Criteria:** See F000 feature doc (AC-A1 through AC-C5)
**Architecture:** Single DeepSeek LLM pass over all customer and collector turns. LLM classifies each turn, results are aggregated into groups with frequency counts. A second LLM call defines willingness levels from the aggregated willingness signals. Output is a single JSON taxonomy file.
**Tech Stack:** Python, DeepSeek API (deepseek-chat), json

---

### Task 1: Data Loader

**Files:**
- Create: `src/f000_keyword_discovery/load_data.py`
- Test: `src/test_load_data.py`

**Step 1: Write the failing test**
Test that `load_records()` returns 31 records from `/data/output_manual.py`, each with `response.dialog` list, and that customer/collector turns can be separated by role.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
`load_records()` imports `results` from `output_manual.py`, returns the list. `get_turns_by_role(records, role)` filters dialog turns.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 2: LLM Client

**Files:**
- Create: `src/infra/llm_client.py`
- Test: `src/test_llm_client.py`

**Step 1: Write the failing test**
Test that `call_deepseek(prompt)` returns a non-empty string. Test that `call_deepseek_json(prompt)` returns a parsed JSON dict. Mock the API call for determinism.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
`call_deepseek(prompt, temperature=0.1)` calls DeepSeek chat API. `call_deepseek_json(prompt)` calls and parses JSON from response. Uses `DEEPSEEK_API_KEY` env var.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 3: Customer Turn Analysis

**Files:**
- Create: `src/f003_reward_labeling/analyze_customer_turns.py`
- Test: `src/test_analyze_customer_turns.py`

**Step 1: Write the failing test**
Test with a mock LLM response that `analyze_customer_turns(records)` returns a dict with `facts` and `emotions` lists. Each entry has `group_name`, `keywords`, `frequency`, `example_turn`, `source`. Test that grouping merges same-meaning keywords.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
- Build prompt: for each customer turn (+ 3-turn context window), ask LLM to classify fact and emotion, output JSON
- Aggregate results: group by semantic similarity (LLM-assisted grouping pass)
- Count frequencies, pick example turns
- Add suggested domain keywords with `source: "suggested"`, `frequency: 0`

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 4: Collector Turn Analysis

**Files:**
- Create: `src/f003_reward_labeling/analyze_collector_turns.py`
- Test: `src/test_analyze_collector_turns.py`

**Step 1: Write the failing test**
Test with mock LLM that `analyze_collector_turns(records)` returns `collector_actions` list with `group_name`, `keywords`, `frequency`, `example_turn`, `source`.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
- Build prompt: for each collector turn, ask LLM to classify action type, output JSON
- Aggregate and group same as Task 3
- Add suggested domain action types

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 5: Willingness Level Definition

**Files:**
- Create: `src/f003_reward_labeling/define_willingness_levels.py`
- Test: `src/test_define_willingness_levels.py`

**Step 1: Write the failing test**
Test with mock LLM that `define_willingness_levels(records)` returns `willingness_levels` list ordered resistant → cooperative. Each level has `level`, `definition`, `boundary`, `example_turns` (each with `text` + `reason`).

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
- First pass: LLM classifies each customer turn's willingness signal
- Second pass: LLM clusters the signals into levels, defines boundaries, picks example turns
- Output ordered list

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 6: Taxonomy Assembly & Output

**Files:**
- Create: `src/f000_keyword_discovery/discover_keywords.py` (main entry point)
- Test: `src/test_discover_keywords.py`

**Step 1: Write the failing test**
Test that running `discover_keywords()` produces `/src/state_keywords.json` with all 4 top-level keys (`facts`, `emotions`, `willingness_levels`, `collector_actions`), all AC from feature doc satisfied.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
Orchestrate Tasks 3-5, assemble into single JSON, write to `/src/state_keywords.json`. Resume-safe: skip already-analyzed turns.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 7: End-to-End Smoke Test

**Files:**
- Test: `src/test_e2e_keyword_discovery.py`

**Step 1: Write the failing test**
Test that `discover_keywords()` runs on actual data (with real DeepSeek API) and output passes all AC-A1 through AC-C5.

**Step 2: Run test to verify it fails** (requires API key)

**Step 3: No new implementation** — just verify existing code works end-to-end

**Step 4: Run test to verify it passes**

**Step 5: Commit**
