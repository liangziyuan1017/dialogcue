# F001: Data Schema Alignment — Implementation Plan

**Feature:** F001 — `docs/features/F001/data-schema-alignment.md`
**Goal:** Map raw records from `/data/output_manual.py` to SOP-aligned schema with `turns_annotated`, `reward`, `state_transitions`, `context`.
**Acceptance Criteria:**
- All 31 records present in output
- Every record has `turns_annotated`, `reward`, `state_transitions`, `context`
- All 9 context fields populated (no nulls in required fields)
- Original dialog data preserved verbatim
**Architecture:** Pure data transformation — read raw records, derive new fields, write aligned output. No LLM calls. Deterministic mapping from `customer_info` to `context` constraint dict.
**Tech Stack:** Python 3, pytest, importlib (for loading .py data files)

---

### Task 1: Context Constraint Mapping

**Files:**
- Create: `src/f001_schema_alignment/align_schema.py`
- Test: `src/test_align_schema.py`

**Step 1: Write failing tests for `build_context()`**
- Test all 9 context fields present and correctly typed
- Test `has_auto_loan` from 他行/我行车贷 fields
- Test `has_mortgage` from 他行/我行房贷 fields
- Test `credit_rating` enum mapping (Z→good, B/2/3→moderate, 0→bad)
- Test `days_delinquent` M1→30
- Test `total_debt` integer parsing
- Test `external_debt` "总余额NNN" parsing
- Test `has_negotiation_history` bool
- Test `available_plans` list extraction
- Test `social_insurance_stable` bool

**Step 2: Run tests to verify they fail**

**Step 3: Implement `build_context()` in `align_schema.py`**

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

---

### Task 2: Turns Annotated + Record Alignment

**Files:**
- Modify: `src/f001_schema_alignment/align_schema.py`
- Modify: `src/test_align_schema.py`

**Step 1: Write failing tests for `align_record()` and `align_all()`**
- Test `turns_annotated` structure (turn_index, role, text)
- Test `reward` is None
- Test `state_transitions` is []
- Test original dialog preserved verbatim
- Test all 31 records present

**Step 2: Run tests to verify they fail**

**Step 3: Implement `build_turns_annotated()`, `align_record()`, `align_all()`**

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

---

### Task 3: Output Generation

**Files:**
- Modify: `src/f001_schema_alignment/align_schema.py`

**Step 1: Write failing test for `write_output_aligned()`**
- Test output file is written with valid Python
- Test output contains 31 records

**Step 2: Run test to verify it fails**

**Step 3: Implement `write_output_aligned()`**

**Step 4: Run test to verify it passes**

**Step 5: Generate `src/f001_schema_alignment/output_aligned.py`**

**Step 6: Commit**
