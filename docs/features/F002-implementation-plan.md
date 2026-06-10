# F002: LLM State Extraction — Implementation Plan

**Feature:** F002 — `docs/features/F002-llm-state-extraction.md`
**Goal:** Extract composite state keywords S = {Emotion + Fact + Willingness} for customer turns and action_type for collector turns via DeepSeek, using F000 taxonomy.
**Acceptance Criteria:**
- Every customer turn has `state_keywords` with at least one tag per dimension (emotion, fact, willingness)
- Every collector turn has `action_type` from F000 taxonomy and `action_text` preserved verbatim
- Labeled turns annotated but flagged
- Resume-safe: re-run skips already-annotated turns
- All 805 turns processed
**Architecture:** Read `output_aligned.py` + `state_keywords.json` → for each unannotated turn, call DeepSeek with taxonomy-constrained prompt → merge results → write `output_states.py`. Two prompt templates: customer (3-dimension extraction) and collector (action classification). Resume-safe via checking existing `state` field.
**Tech Stack:** Python, DeepSeek API (via `llm_client.py`), existing `state_keywords.json` taxonomy

---

### Task 1: Build Taxonomy Index

**Files:**
- Create: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test that `build_taxonomy_index` loads `state_keywords.json` and returns structured dicts: fact_groups, emotion_groups, willingness_levels, collector_action_groups. Each group has `group_name` and `keywords` list.
**Step 2: Run test → verify fail**
**Step 3: Implement `build_taxonomy_index()`** — load JSON, extract group_name+keywords for each dimension.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 2: Customer Turn Extraction Prompt

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test that `build_customer_prompt(turn_text, taxonomy_index)` returns a prompt string containing the turn text and all taxonomy group names for facts, emotions, and willingness levels.
**Step 2: Run test → verify fail**
**Step 3: Implement `build_customer_prompt()`** — construct prompt asking DeepSeek to classify the turn into: one or more fact group_names, one or more emotion group_names, one willingness level. Include full taxonomy as valid options. Request JSON output: `{"facts": [...], "emotions": [...], "willingness": "..."}`.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 3: Collector Turn Extraction Prompt

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test that `build_collector_prompt(turn_text, taxonomy_index)` returns a prompt containing the turn text and all collector action group_names.
**Step 2: Run test → verify fail**
**Step 3: Implement `build_collector_prompt()`** — construct prompt asking DeepSeek to classify the collector turn into one action_type from the taxonomy. Request JSON: `{"action_type": "..."}`.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 4: Single Turn Extraction

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test `extract_turn_state(turn, taxonomy_index)` returns correct structure: for customer → `{"facts": [...], "emotions": [...], "willingness": "..."}`, for collector → `{"action_type": "..."}`. Mock `call_deepseek_json`.
**Step 2: Run test → verify fail**
**Step 3: Implement `extract_turn_state()`** — dispatch to customer or collector prompt, call `call_deepseek_json`, validate response against taxonomy, return structured state.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 5: Batch Processing with Resume

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test `extract_all_states(records, taxonomy_index)` skips turns that already have `state` with content, processes only unannotated turns, and returns all records with complete state annotations.
**Step 2: Run test → verify fail**
**Step 3: Implement `extract_all_states()`** — iterate records → iterate turns → skip if turn has `state` with content → call `extract_turn_state` → assign `state_keywords` for customer / `action_type`+`action_text` for collector → flag labeled turns with `labeled: true`.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 6: Output Writer

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test `write_output_states(records, path)` writes valid Python file with `results = [...]` that can be imported.
**Step 2: Run test → verify fail**
**Step 3: Implement `write_output_states()`** — same pattern as `align_schema.py`: write `results = [` + repr each record + `]`.
**Step 4: Run test → verify pass**
**Step 5: Commit**

---

### Task 7: Main Entry Point & E2E

**Files:**
- Modify: `src/extract_states.py`
- Test: `src/test_extract_states.py`

**Step 1: Write failing test** — test `main()` loads inputs, runs extraction, writes output. Mock LLM calls. Verify output file exists and all 805 turns have state.
**Step 2: Run test → verify fail**
**Step 3: Implement `main()`** — `if __name__ == "__main__"` block that loads `output_aligned.py` + `state_keywords.json`, calls `extract_all_states`, calls `write_output_states`.
**Step 4: Run test → verify pass**
**Step 5: Commit**
