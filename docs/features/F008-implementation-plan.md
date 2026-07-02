# F008: State Extraction Module — Implementation Plan

**Feature:** F008 — `docs/features/F008-state-extraction.md`
**Goal:** Create `state_extraction.py` with LLM-first state extraction, PostgreSQL keyword fallback, and state accumulation with dedup.
**Acceptance Criteria:** See F008 feature doc
**Architecture:** LLM (DeepSeek) extracts facts/emotions/actions from utterance given taxonomy. Keyword scan via PostgreSQL tsvector as fallback. `merge_state()` for accumulation with dedup and order preservation.
**Tech Stack:** Python, DeepSeek API, asyncpg (runtime tsvector FTS) + psycopg2 (build-time)

---

### Task 1: LLM State Extraction

**Files:**
- Create: `src/f008_state_extraction/state_extraction.py`
- Test: `src/tests/f006_retrieval_engine/test_state_extraction.py`

**Step 1:** Write failing test for `extract_state_llm(utterance, taxonomy)` returning `{facts, emotions, actions, confidence, method: "llm"}`. Mock DeepSeek API call.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement `extract_state_llm()`: build prompt with taxonomy context, call DeepSeek, parse JSON response into canonical group names.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 2: Keyword Fallback Extraction

**Files:**
- Modify: `src/f008_state_extraction/state_extraction.py`
- Modify: `src/tests/f006_retrieval_engine/test_state_extraction.py`

**Step 1:** Write failing test for `extract_state_keyword(utterance, taxonomy)` returning `{facts, emotions, actions, confidence, method: "keyword"}`. Mock PostgreSQL tsvector FTS.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement `extract_state_keyword()`: tokenize utterance, query `taxonomy_keywords` table via tsvector match, aggregate results by group_name.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.

---

### Task 3: Unified extract_state + merge_state

**Files:**
- Modify: `src/f008_state_extraction/state_extraction.py`
- Modify: `src/tests/f006_retrieval_engine/test_state_extraction.py`

**Step 1:** Write failing test for `extract_state()` — LLM first, keyword on failure. Write failing test for `merge_state()` — dedup + order preservation.

**Step 2:** Run test to verify it fails.

**Step 3:** Implement `extract_state()`: try LLM, catch exception → keyword fallback. Implement `merge_state()`: set-union semantics with first-seen order preservation.

**Step 4:** Run test to verify it passes.

**Step 5:** Commit.
