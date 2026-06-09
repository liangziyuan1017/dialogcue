# Feature-Wise Implementation Plan: Debt Collection Script Recommendation System

## Overview

Decompose the phase-based plan into independently developable features. Each feature states its goal, passing criteria, and dependencies. All new code lives under `/src`. Data input is `/data/output_manual.py`.

---

## Dependency Graph

```
F000 ──► F001 ──► F002 ──► F003 ──► F004 ──► F005 ──► F006
                                                    │
                                             F007 ──┘
```

---

## F000: State Keyword Discovery

**Depends on:** None

**Goal:** Analyze all turns across 31 records to discover the actual state keyword landscape from data. Group same-meaning keywords into canonical groups (e.g. "没钱", "经济困难" → group `financial_hardship`). Discover **fact groups**, **emotion groups**, **collector action groups**, and **willingness levels** (count determined by data clustering). Include suggested domain-common keywords not observed in 31 records. Output taxonomy to `/src/state_keywords.json` that F002 will consume.

**Passing criteria:**
- `state_keywords.json` contains `facts`, `emotions`, `willingness_levels`, `collector_actions` arrays
- Each group has `group_name`, `keywords` (variant list), `frequency`, `example_turn`, `source` ("observed" or "suggested")
- Groups sorted by frequency descending; suggested after observed
- Total observed fact groups ≥ 5, total observed emotion groups ≥ 5, total observed collector action groups ≥ 4
- Willingness levels ordered most resistant → most cooperative; count is data-driven
- Each willingness level has `level`, `definition`, `boundary`, `example_turns` (≥2 with `text` + `reason`)
- Every `example_turn` traces to an actual turn in `/data/output_manual.py`
- Suggested domain keywords included with `source: "suggested"`, `frequency: 0`

---

## F001: Data Schema Alignment

**Depends on:** F000

**Goal:** Map raw records from `/data/output_manual.py` to SOP-aligned schema — derive `turns_annotated`, `reward` (null), `state_transitions` (empty), and `context` constraint dict from `customer_info` fields. Output to `/src/output_aligned.py`.

**Passing criteria:**
- All 31 records present
- Every record has `turns_annotated`, `reward`, `state_transitions`, `context`
- All 9 context fields populated (no nulls in required fields)
- Original dialog data preserved verbatim

---

## F002: LLM State Extraction

**Depends on:** F001

**Goal:** For each customer turn, extract composite state keywords `S = { Emotion + Fact + Willingness }` via DeepSeek, using the taxonomy from F000 as the target set. For each collector turn, extract `action_type` from the discovered taxonomy (F000) and preserve `action_text` verbatim. Output to `/src/output_states.py`.

**Passing criteria:**
- Every customer turn has `state_keywords` with at least one tag per dimension (emotion, fact, willingness)
- Every collector turn has `action_type` from the F000 discovered taxonomy and `action_text` preserved verbatim
- Labeled turns (label="1") annotated but flagged
- Resume-safe: re-run skips already-annotated turns
- All 805 turns processed

---

## F003: Reward Labeling

**Depends on:** F002

**Goal:** Determine R ∈ {0, 1} per conversation — LLM detects repayment commitment triggers in final turns, performs counterfactual verification to credit the preceding collector action, cross-validates against `plan_evaluation`. Output to `/src/output_rewarded.py`.

**Passing criteria:**
- Every record has `reward` ∈ {0, 1}
- Every R=1 record has `reward_evidence` and `reward_action_credit`
- R=1 records consistent with `plan_evaluation` (mismatches flagged as warnings)
- No R=0 record has `reward_action_credit`

---

## F004: Decision Tree Construction

**Depends on:** F003

**Goal:** Build state-transition decision tree from annotated conversations — extract paths `S₀ → a₀ → S₁ → a₁ → ... → Sₙ`, merge identical/near-identical state sequences, accumulate historical collector sentences at each node, implement fallback via progressive tag removal. Output to `/src/decision_tree.json`.

**Passing criteria:**
- Tree has root node with `state_id: "initial_contact"`
- Every leaf node has non-empty `sentence_pool`
- Every sentence entry has `script_text`, `script_id`, `source_call_ids`
- All 31 conversations represented (every call_id in at least one `source_call_ids`)
- Keywords lexicographically sorted at every node

---

## F005: Context Tagging & Quality Scoring

**Depends on:** F004

**Goal:** Tag each sentence with `bg_constraints` from source conversation's customer profile, encode as bitmask for O(1) filtering. Compute HWR (Laplace-smoothed) and SAS (DeepSeek embedding cosine similarity). UC and CSI deferred. Output to `/src/decision_tree_scored.json`.

**Passing criteria:**
- Every sentence has `bg_constraints` dict with all 5 bitmask fields
- Every sentence has `bg_bitmask` integer
- Every sentence has `win_rate` (HWR_smoothed) ≥ 0
- Every sentence has `sas` ≥ 0
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset

---

## F006: Retrieval & Ranking Engine

**Depends on:** F005

**Goal:** Build `recommend()` function — given real-time customer utterance + context, extract state via LLM, traverse decision tree (exact → fallback → soft match via embeddings), hard-filter by bitmask, rank by HWR (primary) + SAS (secondary), return top-1 script. Output to `/src/retrieval_engine.py`.

**Passing criteria:**
- `recommend()` returns `{ script_text, state_id, win_rate, confidence }`
- Exact state match returns sentence from matched node's pool
- Fallback (tag removal) returns sentence from sub-state node
- Soft matching returns sentence from semantically closest node
- Context filtering excludes sentences with incompatible bitmask
- Ranking prefers higher HWR; SAS breaks ties

---

## F007: Scaling Architecture Design

**Depends on:** F005

**Goal:** Document migration path from 31 → 10,000 records — PostgreSQL schema, DeBERTa fine-tuning (Solution A), Milvus/pgvector index (Solution B), batch metrics pipeline, ONNX + C++ trie optimization. Output to `/src/scaling_architecture.md`.

**Passing criteria:**
- Covers all 5 migration steps
- Each step has before/after architecture
- Latency targets stated (Solution A: <500ms, Solution B: <2s)
- Data format migration from `.py` to PostgreSQL DDL specified
