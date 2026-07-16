# F004 + F005: Tree Building Fix & Additive Merge Plan

**Created:** 2026-07-07
**Authority:** `SCBGE_GUIDELINE.md` (overall flow + ADR index) and `docs/features/` (per-feature ACs). This plan aligns with both; where they conflict, the guideline wins and the feature doc is updated to match.
**Scope:** Fix **only** the tree construction (F004, guideline Step 1.5) and scoring (F005, guideline Step 1.6) scripts so all acceptance criteria are met, and restructure building to be **additive** so new data merges into an existing tree without a full rebuild (guideline Scaling Path: "incremental rebuild of affected subtrees on new data").
**Input:** `f003_reward_labeling/data/output_rewarded.py` — used as-is. Everything up to and including reward labeling is correct (user's restructure: relabel moved into F001 before reward). No pipeline re-run; no loader change.
**Constraint:** Fix scripts, not data. No hand-editing of `decision_tree.json` or `decision_tree_scored.json`.

### Scope boundary — NOT touched by this plan

| Feature | Reason | If impact found |
|---|---|---|
| F000–F003 | Upstream of tree; user confirmed correct | — |
| F006 (retrieval/ranking) | Downstream consumer of `decision_tree_scored.json` | **Flag for user decision** — bitmask 5-field revert changes range 0–1023→0–31; F006's `compute_bitmask_score` is field-count-agnostic but fixtures/tests may need updating. Do not change F006 without user approval. |
| F007/F007b (infra/DB) | Downstream; embeddings are DB-only per guideline | **Flag for user decision** — no change planned, but verify DB schema `embedding vector(1024)` still matches if embedding dim changes. |
| F008/F009/F010 | Online retrieval/UI; no tree-structure dependency | **Flag for user decision** — almost no change expected; if the additive tree changes node `path_signature` format, F008 node lookup may need a compatibility check. User decides. |
| `whole_pipeline.py` | User already restructured; do not re-run | — |

---

## 0. Guideline Alignment Map

| Plan section | Guideline reference | Alignment action |
|---|---|---|
| Phase 1–2 (F004 additive) | Step 1.5 (lines 442–541), ADR-011/015/016/017/021/022/023 | Update Step 1.5 to describe additive building; mark ADR-015/017/018/022/023 superseded by ADR-029/030 |
| Phase 3 (node HWR) | Step 1.6 "HWR with node-level aggregation" (line 553) | Guideline already documents blending; code gap — implement to match |
| Phase 3 (bitmask 5-field revert) | Step 1.6 ADR-020 "10-bit bitmask… Expanded 5→10 on 2026-06-22" (line 551), Architecture Decisions Summary (line 115) | Revert code to 5; update guideline + ADR-020 to reflect revert. **F006 downstream impact → user decision** |
| Phase 3 (embedding) | Step 1.6 note (line 627): "Embeddings persisted to PostgreSQL only… stripped from JSON… backward compat when db=None" | **No code fix** — current behavior matches guideline. Update F005 doc AC to match guideline (embedding → DB-only, not in JSON) |
| Embedding dimension | Step 1.6 (line 547): "bge-m3 (1024-dim)", ADR-024 | F005 doc says 768 (DeepSeek) — update doc to 1024 (bge-m3) per guideline |
| Phase 4 (invariant tests) | (no guideline ref — new) | Add artifact-level tests; no guideline change |
| Phase 5 (F004→F005 wiring) | Scaling Path (line 1599) | Additive merge realizes the scaling path's "incremental rebuild". Only `build_and_score_tree.py`; do not touch `whole_pipeline.py` |

---

## 1. Root Causes (from analysis)

### F004 — `tree_transforms.py:_split_by_action` (one bug, two symptoms)

The guard `if not force_split and len(by_action) <= 1: return` action-splits any non-fact/emotion node that holds >1 distinct `collector_action`. This is shape-based role inference — root and `normal_end` match the "not a fact/emotion parent" shape and get split:

- **Opening greetings leave root:** 231 opening sentences move into `a:greeting` child; root pool keeps 0. Violates AC "Root node sentence_pool entries have `gesture_type: opening`".
- **Endings leave `normal_end`:** `_consolidate_endpoints` collects 110 ending sentences, then `_split_by_action` re-scatters them into `a:closure`/`a:pressure`/… children; `normal_end` keeps 6. Violates design "all ending sentences collected into a single normal_end node".

Secondary: the ending-mark loop marks `seg["sentences"]` entries that `_merge_sentences` may have already discarded in favor of an existing pool entry (reference aliasing), so some endings are never marked.

### F005 — one missing implementation, one spec drift, one non-bug

- **`win_rate_node` never set; no blending (BUG).** The guideline (Step 1.6, line 553) documents: "HWR with node-level aggregation: blend `weight * sentence_hwr + (1-weight) * node_hwr` where `weight = n/(n+2)`." The code's `compute_hwr` computes sentence-level Laplace HWR only; node-level aggregation and blending are unimplemented. All 782 sentences lack `win_rate_node`. This is a code-vs-guideline gap.
- **Bitmask 10→5 drift (REVERT).** The guideline (ADR-020, line 551) says "10-bit bitmask… Expanded 5→10 on 2026-06-22." The F005 feature doc specifies 5 fields (range 0–31). The 10-field expansion was an undocumented drift from the original design. Revert code to 5; update guideline + ADR-020 to reflect the revert.
- **Embedding absent from JSON (NOT A BUG).** The guideline (line 627) explicitly states: "Embeddings (1024-dim bge-m3 vectors) are persisted to PostgreSQL only. `decision_tree_scored.json` strips vectors before dump to keep the file small; the `embedding` field is absent from the JSON." And "optional embedding in `score_tree.py` (backward compat when `db=None`)." The standalone pipeline runs with `db=None` → no embeddings in JSON → **this is the intended backward-compat mode.** The F005 doc AC "Every sentence has `embedding` field" contradicts the guideline; update the doc to match the guideline.

### Why the bugs shipped

183 unit tests pass, but none loads the generated JSON and checks an acceptance criterion. The suite tests functions in isolation; the artifact is unverified.

### Input (no action needed)

The user's pipeline restructure already solved the staleness: `relabel_state.py` moved to `f001_schema_alignment/`, runs before reward, overwrites `output_aligned.py` with relabeled tags. `output_rewarded.py` is produced from relabeled data → has correct tags + reward. `output_relabeled.py` is deleted. The tree already reads `output_rewarded.py` (`build_decision_tree.py:49`, `score_tree.py:33`). **No loader change, no pipeline re-run.** Everything up to and including reward labeling is correct; this plan fixes only F004 + F005.

Guideline note: the user updated the SCBGE_GUIDELINE.md data flow to show relabel overwriting `output_aligned.py`, but labels it "F003 (state relabeling)" — the code is in `f001_schema_alignment/relabel_state.py`, so the guideline label should say "F001".

---

## 2. Design: Additive Tree Building

### Goal

Replace the "build raw tree → run 6 global fix-up transforms" pipeline (guideline Step 1.5, ADR-011/015/017/021/022/023) with an **additive inserter** that places each sentence in its final home at insert time. The tree becomes a persistent artifact that grows dialog-by-dialog. This realizes the guideline Scaling Path (line 1599): "incremental rebuild of affected subtrees on new data."

### Base structure

```
initial_contact (root, role="opening")
├── normal_end (role="ending")
└── abrupt_end  (role="ending")
```

Created once. All dialogs add paths between root and the end nodes. Matches guideline Step 1.5: "exactly 1 opening root + 2 consolidated end nodes as direct children of root."

### `add_dialog_to_tree(tree, record, registry)`

Atomic per-dialog insertion. After it returns, the tree is self-consistent for that dialog — no global post-pass required.

```
1. Ensure base structure (root, normal_end, abrupt_end) exists.
2. Greeting turns → root.sentence_pool (gesture_type="opening", collector_action="greeting").
   These never move. Root is never action-split.
3. Extract segments (existing _extract_segments, unchanged).
4. For each segment, walk facts then emotions one at a time (ADR-016: fact-by-fact walking):
     match = find child of current_node with branch_key == single_bk
     if match and not creates_cycle(match, current_node):   # ADR-021 cycle protection
         current_node = match          # reuse (DAG share)
     else:
         spawn new child under current_node (role="decision")
         registry[identity] = new child
     accumulated_facts/emotions updated.
5. Place segment sentences in their FINAL home at insert time:
      - If current_node is a fact/emotion parent (role="decision"):
          group sentences by collector_action;
          each action group → a:{action} child (role="action"), created or reused;  # ADR-017 at insert
          unassigned sentences → current_node.sentence_pool.
      - If current_node is root:
          sentences stay in root.sentence_pool (no action split on root).
6. Closing sentences (action in CLOSING_ACTIONS) → normal_end.sentence_pool
   (gesture_type="ending"), NOT placed in the decision node. Mark on the
   actual pool entry kept by _merge_sentences, not the discarded input.
7. If no closing found in dialog → ensure abrupt_end exists (base structure guarantees it).
8. Update inherited_facts, inherited_emotions, node_id on the touched path.  # ADR-021 identity
```

### Reconciliation (cross-dialog, lightweight)

Two concerns are cross-dialog and can't be fully resolved myopically. Handle them as **idempotent local checks inside the inserter**, not global passes:

- **Redundant fact/emotion (ADR-018/022):** before spawning a fact child, check if the fact is in `accumulated_facts` (parent chain). If so, skip spawn, continue under current_node. This folds `_collapse_redundant_facts` into the insert decision.
- **Sibling dedup (ADR-021):** before spawning, scan current_node's children for matching identity. If found, reuse. (Already done via `node_registry`; keep the registry as a parameter so it survives across dialogs.)

### Incremental merge entry point

```
merge_dialogs(tree_path, new_records):
    tree = load(tree_path) if exists else make_base_tree()
    registry = build_registry_from_tree(tree)   # reconstruct identity→node map
    for record in new_records:
        add_dialog_to_tree(tree, record, registry)
    save(tree, tree_path)
```

`build_tree(records)` becomes: `merge_dialogs(path, records)` starting from empty. Full rebuild = delete the tree file + merge all. Incremental = merge only new call_ids.

### What gets deleted

The global post-transform chain in `write_decision_tree` is removed (supersedes ADR-015/017/018/022/023 transform approach):
- `_split_composite_nodes` — composites never created (ADR-016 fact-by-fact walking).
- `_merge_sibling_facts` — sibling dedup handled at insert.
- `_collapse_redundant_facts` — folded into insert decision (ADR-018/022).
- `_split_by_action` — action split done at insert, scoped to decision nodes only (ADR-017).
- `_deduplicate_nodes` — sibling dedup at insert (ADR-021).
- `_propagate_facts` — `inherited_facts`/`node_id` maintained incrementally on the touched path.
- `_consolidate_endpoints` — endings placed directly into `normal_end` at insert.
- `_ensure_leaf_termination` — removed (was creating duplicate `abrupt_end` nodes per leaf). Replaced by `_link_leaves_to_abrupt_end` + `_remove_stray_abrupt_ends`; leaves without children are implicitly terminated at root's `abrupt_end`.

`_sort_keywords` remains as a cheap final touch. `_propagate_sentences` was removed from `build_tree` (test helper) for consistency with `write_decision_tree` (production), which never used propagation — empty-pool nodes are handled at retrieval time by `descend_for_sentences` (ADR-034).

**`_collect_tree_sentences` dedup by `node_id`** (`score_tree.py`): `add_dialog_to_tree` reattaches existing registry nodes under new parents, forming an in-memory DAG. `json.dump` deep-copies shared subtrees into the serialized JSON, so `_collect_tree_sentences` (which feeds `build_tree_and_db` / `add_records` embedding) re-counted and re-embedded each copy. The walk now skips any `node_id` already visited, collapsing duplicates to unique nodes. This is the root-cause fix for the sentence-count inflation observed at scale (840,000 placements → ~28,000 unique at 1,700 records). JSON storage still contains deep-copied subtrees (harmless to retrieval); embedding and DB writes drop to unique `script_id`s.

### Role tagging (ADR-030, new)

Every node gets `role ∈ {"opening", "ending", "decision", "action"}` at creation. Any surviving transform checks `role` and skips non-decision/action nodes. This is the safety net that prevents the `_split_by_action` bug class from recurring.

---

## 3. Phased Tasks

### Phase 1: Role tagging + base structure (F004) — guideline Step 1.5, ADR-011

**Files:**
- `src/f004_decision_tree/tree_transforms.py`
- `src/f004_decision_tree/build_decision_tree.py`
- `src/tests/f004_decision_tree/test_build_decision_tree.py`

**Steps:**
1. Write failing test: every node has `role` in `{"opening","ending","decision","action"}`; root role="opening"; end nodes role="ending".
2. Add `role` to node creation sites: root→"opening", fact/emotion children→"decision", action children→"action", end nodes→"ending".
3. In `_split_by_action`: `if node.get("role") != "decision": return` (skip root/end/action nodes). This immediately fixes the opening-greeting and ending-consolidation bugs even before the additive refactor.
4. Fix ending-mark aliasing: in `build_tree`, mark `gesture_type="ending"` on the pool entries that `_merge_sentences` actually kept. Change the order: mark `seg["sentences"]` **before** `_merge_sentences`, or have `_merge_sentences` propagate `gesture_type` from new→existing when merging.
5. Run tests.

**Verify:** Root pool contains all `gesture_type:"opening"` sentences; `normal_end` pool contains all `gesture_type:"ending"` sentences; no ending sentences outside end nodes.

---

### Phase 2: Additive inserter (F004) — guideline Step 1.5, Scaling Path

**Files:**
- `src/f004_decision_tree/build_decision_tree.py` — add `add_dialog_to_tree()`, `make_base_tree()`, `build_registry_from_tree()`, `merge_dialogs()`
- `src/tests/f004_decision_tree/test_additive.py` (new)

**Steps:**
1. Write `make_base_tree()` → root + normal_end + abrupt_end with roles.
2. Write `add_dialog_to_tree(tree, record, registry)` per §2 design. Action split at insert (scoped to decision nodes). Endings → normal_end. Greetings → root. Redundant-fact skip. Sibling dedup via registry.
3. Write `build_registry_from_tree(tree)` → walk tree, populate `{identity: node}`.
4. Write `merge_dialogs(tree_path, new_records)` → load-or-create, add each, save.
5. Refactor `build_tree(records)` to call `merge_dialogs` with a temp path (in-memory).
6. Refactor `write_decision_tree()` to use `merge_dialogs` with the real file path. Remove the 6 global post-transforms. Keep `_sort_keywords` as a final touch.
7. **Idempotency test:** `add_dialog_to_tree` called twice with the same record produces the same tree (no duplicate sentences, no duplicate nodes).
8. **Incremental test:** build tree from records[0:N//2], save, then `merge_dialogs` with records[N//2:]; assert equal to building from all N at once (where N = full record count).
9. **AC invariant tests** (see Phase 4).

**Verify:** `python3 -m f004_decision_tree.build_decision_tree` produces `decision_tree.json` with full call_id coverage; root has opening greetings; normal_end has endings; no global transforms in call stack.

---

### Phase 3: F005 scoring fixes — guideline Step 1.6, ADR-020/024

**Files:**
- `src/f005_context_scoring/scoring_metrics.py` — add `compute_node_hwr`; keep `BITMASK_FIELDS` at 10 (user decision)
- `src/f005_context_scoring/score_tree.py` — node HWR + blending
- `src/tests/f005_context_scoring/test_score_tree.py`

**Steps:**
1. **Node HWR + blending (implements guideline line 553):**
   - Add `compute_node_hwr(sentence_pool, reward_lookup)` → union of all `source_call_ids` in pool → Laplace `(wins+α)/(total+β)`.
   - In `_score_sentence_pool`: compute `node_hwr` once per pool; for each sentence compute `sentence_hwr = compute_hwr(call_ids, ...)`, `weight = n/(n+2)`, `win_rate = weight*sentence_hwr + (1-weight)*node_hwr`, set `win_rate_node = node_hwr`.
   - Edge case: empty pool → skip. Single sentence → `weight` small, node dominates (correct per guideline).
2. **Bitmask field count — revert to 5 (code fix, aligns with original F005 design + ADR-006's 5 boolean-derivable fields):** `BITMASK_FIELDS` in `scoring_metrics.py` currently has 10 fields. Revert to the 5 fields specified in the F005 design:

   | Bit | Field | Source |
   |-----|-------|--------|
   | 0 | `has_auto_loan` | `context.has_auto_loan` |
   | 1 | `has_mortgage` | `context.has_mortgage` |
   | 2 | `has_negotiation_history` | `context.has_negotiation_history` |
   | 3 | `social_insurance_stable` | `context.social_insurance_stable` |
   | 4 | `credit_rating_good` | `context.credit_rating == "good"` |

   - Remove the 5 extra fields (`card_restricted`, `is_cash_out_customer`, `has_complaint_history`, `has_legal_tools`, `is_negotiation_brain_customer`) from `BITMASK_FIELDS` and `_extract_bg_constraints`.
   - `bg_bitmask_int` range returns to 0–31.
   - Drop the extra fields from `_extract_bg_constraints` output so `bg_constraints` has exactly 5 keys matching the spec. The extra context fields remain available in the `context` dict (ADR-006: 21 fields) for `bg_background` / range filtering, just not bitmask-encoded.
   - This is a **code revert** to match the original design doc; the F005 doc stays as-is (5 fields, 0–31). The guideline + ADR-020 are updated to reflect the revert.
3. **Embedding — NO CODE FIX (aligns with guideline line 627):** The guideline explicitly states embeddings are "persisted to PostgreSQL only… `decision_tree_scored.json` strips vectors before dump… backward compat when `db=None`." The standalone pipeline (`build_and_score_tree.py`) runs with `db=None` → no embeddings in JSON → **intended behavior.** The F005 doc AC "Every sentence has `embedding` field" is updated to match the guideline (see §4). The full DB-loaded path (`write_scored_tree` with `db`) already computes embeddings via `embed_texts` and upserts to PostgreSQL — no change needed.
4. Write failing tests for `win_rate_node` presence + blend formula; `bg_constraints` has exactly 5 keys; `bg_bitmask_int` ∈ [0,31].

**Verify:** Every sentence in `decision_tree_scored.json` has `win_rate_node` ∈ [0,1], `win_rate` = blend, `bg_constraints` with 5 keys, `bg_bitmask_int` ∈ [0,31]. Embeddings absent from JSON (per guideline), present in PostgreSQL when `db` is passed.

---

### Phase 4: Artifact-level invariant tests (the real safety net)

**Files:**
- `src/tests/f004_decision_tree/test_tree_invariants.py` (new)
- `src/tests/f005_context_scoring/test_scored_invariants.py` (new)

**Steps:** Tests that load the generated JSON files and assert every F004/F005 acceptance criterion:

F004 invariants:
- Root `state_id == "initial_contact"`, `role == "opening"`.
- Root pool contains every `gesture_type:"opening"` sentence in the tree.
- `normal_end` pool contains every `gesture_type:"ending"` sentence (no endings scattered outside end nodes).
- Exactly one `normal_end`, one `abrupt_end`, both direct children of root.
- Every leaf terminates at an end node.
- Every sentence has `script_text, script_id, source_call_ids, customer_willingness, collector_action, fact_context`.
- All call_ids from `output_rewarded.py` appear in ≥1 `source_call_ids`.
- Keywords sorted at every node; no composite branch keys; no redundant fact/emotion nodes; every node has `node_id, inherited_facts, inherited_emotions, role`.
- Single-child ratio < 85%.

F005 invariants:
- Every sentence has `bg_constraints` with exactly 5 keys (`has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good`), `bg_bitmask`, `bg_bitmask_int` ∈ [0,31].
- `win_rate ∈ [0,1]`, `win_rate_node ∈ [0,1]`, `sas ∈ [0,1]`.
- `win_rate == weight*sentence_hwr + (1-weight)*win_rate_node` (recompute and compare).
- `embedding` absent from JSON (per guideline — DB-only); assert `conversation_context` present (the embedding input).
- `uplift_score == 0`, `csi == 0`, `deferred == True`.
- Bitmask AND filtering correctness on a sample.

**Verify:** `pytest tests/f004_decision_tree/test_tree_invariants.py tests/f005_context_scoring/test_scored_invariants.py` all pass.

---

### Phase 5: F004→F005 wiring only — guideline Scaling Path

**Files:**
- `src/f005_context_scoring/build_and_score_tree.py` (only this file; do NOT touch `whole_pipeline.py`)

**Steps:**
1. Use `merge_dialogs` (additive) instead of `write_decision_tree` (full rebuild) when the tree file already exists. Add a `--rebuild` flag to force full rebuild from scratch.
2. Run `build_and_score_tree.py` end-to-end on the existing `output_rewarded.py`. Embedding step runs only when `db` is passed (guideline backward-compat); standalone JSON output has no embeddings (per guideline).

**Verify:** `python3 -m f005_context_scoring.build_and_score_tree` completes; `decision_tree.json` has full call_id coverage; `decision_tree_scored.json` has `win_rate_node` + 5-field bitmask; no `embedding` field in JSON (DB-only per guideline).

---

## 4. Documentation Changes

### `SCBGE_GUIDELINE.md` (the overall flow — authoritative)

- **Data Flow diagram (lines 72–101):** user already updated — relabel now overwrites `output_aligned.py` before reward. Fix label: "F003 (state relabeling)" → "F001 (state relabeling)" since `relabel_state.py` moved to `f001_schema_alignment/`. `output_rewarded.py` → F004 stays correct (now has relabeled tags).
- **Step 1.5 (F004, lines 442–541):**
  - "Input: `output_rewarded.py`" — stays correct (now has relabeled tags after user's pipeline restructure).
  - Rewrite "Process" to describe additive building (`add_dialog_to_tree`, `merge_dialogs`), role tagging, action-split-at-insert. Remove the "fact-by-fact walk → transforms → dedup" description.
  - Update tree statistics (node count, sentence count, call_ids full coverage) after regenerating from the full dataset.
- **Step 1.6 (F005, lines 543–627):**
  - "10-bit `bg_bitmask`" → "5-bit `bg_bitmask`" (revert ADR-020 expansion).
  - Update the `bg_constraints` / `bg_bitmask` JSON samples (lines 579–602) to show 5 fields, not 10.
  - "HWR with node-level aggregation" (line 553): no change — guideline already correct; code now implements it.
  - Embedding note (line 627): no change — guideline already correct; F005 doc updated to match.
- **Architecture Decisions Summary (line 115):** "Context constraints | 21-field mapping → 10-bit bitmask | ADR-006, ADR-020" → "→ 5-bit bitmask".
- **ADR Index (lines 1615–1649):**
  - ADR-020: update "10-bit bitmask… Expanded 5→10 on 2026-06-22" → "5-bit bitmask (reverted from 10 on 2026-07-07 per ADR-032)".
  - ADR-015/017/018/022/023: mark "Superseded by ADR-029 (additive building)".
  - Add ADR-029/030/031/032 entries.
- **Scaling Path (line 1599):** "incremental rebuild of affected subtrees" → reference `merge_dialogs` as the realization.

### `docs/features/F004-decision-tree-construction.md`
- Update `status`: `complete` → `in-progress` (during fix) → `complete` (after verification).
- Update `updated` date.
- **Current Tree Statistics** section: regenerate from full-dataset output (node count, gesture counts, call_ids full coverage, branch keys).
- **Design Decisions**: add entry for additive building (`add_dialog_to_tree`, `merge_dialogs`), role tagging, action-split-at-insert. Remove or annotate the "global post-transform" decisions (`_split_by_action`, `_collapse_redundant_facts`, etc.) as superseded by ADR-029/030.
- **Acceptance Criteria**: uncheck all `[x]` → re-check after Phase 4 passes. Add new AC: "Tree supports incremental merge — `merge_dialogs` on new records extends existing tree without rebuild."
- **Files** table: add `merge_dialogs` mention; remove deleted transform references if any functions are removed.
- **Dependencies**: input is `output_rewarded.py` (F003, now with relabeled tags).

### `docs/features/F004-implementation-plan.md`
- Add a section pointing to this plan (`F004-F005-tree-fix-plan.md`) for the additive refactor.
- Mark the global-transform tasks as superseded.

### `docs/features/F005-context-tagging-quality-scoring.md`
- Update `status` and `updated`.
- **Bitmask fields table**: no change — the doc already specifies the correct 5 fields. The code revert brings the implementation back in line with the doc.
- **Embedding AC**: update "Every sentence has `embedding` field (768-dim float32 list from DeepSeek embedding API)" → "Embeddings (1024-dim bge-m3 vectors) are persisted to PostgreSQL only; `decision_tree_scored.json` strips vectors before dump (per SCBGE_GUIDELINE.md Step 1.6). The `conversation_context` field is present in JSON as the embedding input." This aligns the doc with the guideline.
- **Embedding dimension**: 768 (DeepSeek) → 1024 (bge-m3) per guideline + ADR-024.
- **Acceptance Criteria**: uncheck → re-check after fix (the existing ACs for 5 fields / 0–31 are now correct and will pass). Add AC: "Every sentence has `win_rate_node`", "`win_rate` blends sentence + node HWR". Update embedding AC per above.
- **Design Decisions**: add node-HWR blending entry; note embedding is DB-only per guideline (ADR-024); note that the 10-field bitmask expansion was reverted to the original 5-field design (ADR-032).
- **Dependencies**: input is `output_rewarded.py` (F003, now with relabeled tags).

### `docs/features/F005-implementation-plan.md`
- Add tasks for node HWR, bitmask field revert to 5, embedding AC doc update (align with guideline).

### `docs/decisions/` (new ADRs)
- **ADR-029-additive-tree-building.md** — Decision to switch from global-post-transform to additive per-dialog insertion. Rationale: eliminates place-then-move bug class; enables incremental merge for new data (guideline Scaling Path). Supersedes ADR-015/017/018/022/023 transform-chain approach.
- **ADR-030-node-role-tagging.md** — Decision to tag every node with `role ∈ {opening, ending, decision, action}` and have all transforms/inserters respect roles. Rationale: shape-based role inference caused `_split_by_action` to corrupt root and end nodes.
- **ADR-031-node-hwr-blending.md** — Decision to compute node-level HWR and blend with sentence-level per guideline Step 1.6. (Amend ADR-020 if it already covers scoring.)
- **ADR-032-bitmask-5-field-revert.md** — Decision to revert `BITMASK_FIELDS` from 10 to the original 5 fields per F005 design. Rationale: the 10-field expansion (ADR-020, 2026-06-22) was an undocumented drift; the original design intentionally bitmask-encodes only the 5 boolean-derivable fields (ADR-006), keeping numeric/list fields in `bg_constraints` dict for later range/list filtering.

### `config.md`
- No change. `embedding.dimension: 1024` is correct per guideline (bge-m3). The F005 doc's "768-dim" is updated to 1024 to match.

### `AGENTS.md` / `.opencode/AGENTS.md`
- No change unless the additive merge introduces a new capability that should be routed. If a `merge_dialogs` CLI is added, consider a registry entry.

---

## 5. Execution Order

```
Phase 1 (role tagging)         → verify opening/ending bugs fixed on current tree
Phase 4 (invariant tests)     → write tests first, watch them fail on current output
Phase 2 (additive inserter)   → verify full-dataset tree, incremental idempotency
Phase 3 (F005 scoring)        → verify win_rate_node + 5-field bitmask
Phase 5 (F004→F005 wiring)    → end-to-end via build_and_score_tree.py only
Phase 4 (re-run)              → all invariants pass
Doc updates (guideline Step 1.5/1.6 + F004/F005 + ADRs) → after code verified
```

No `whole_pipeline.py` re-run. No F006–F010 code changes (flagged for user decision if impact found).

Phase 4 (invariant tests) is written **before** Phase 2 so the additive refactor is guided by failing-then-passing artifact tests, not just unit tests.

---

## 6. Risks & Rollback

- **Additive ≠ full rebuild for cross-dialog dedup:** if the inserter's myopic redundant-fact check misses a case that the old global `_collapse_redundant_facts` caught, the tree may grow extra branches. Mitigation: keep `_collapse_redundant_facts` as an optional `--reconcile` pass runnable after incremental merges; invariant tests catch regressions.
- **Full dataset may surface new facts/emotions/actions** not in the 31-record subset. The inserter handles this naturally (new branch keys spawn new nodes). Verify the keyword taxonomy (F000) covers them.
- **F006 downstream impact (→ user decision):** F006 retrieval uses `bg_bitmask_int` for soft scoring (guideline Step 2.5). Reverting 5 fields changes the bitmask range 0–1023 → 0–31. F006's `compute_bitmask_score` is field-count-agnostic (`matched_bits/required_bits`), so likely no F006 code change — but F006 tests/fixtures with 10-bit expectations may need updating. **Do not change F006 without user approval.** Flag: check `src/f006_retrieval_ranking/` for hardcoded 10-field assumptions and report to user.
- **F007/F008/F009/F010 impact (→ user decision):** almost none expected. The additive tree preserves `path_signature` format (F008 node lookup). Embedding dim stays 1024 (F007 DB schema unchanged). If any incompatibility is found, **flag for user decision** — do not change these features.
- **Rollback:** all changes are in `build_decision_tree.py`, `tree_transforms.py`, `score_tree.py`, `scoring_metrics.py`, `build_and_score_tree.py`. Revert these files to restore the 31-record global-transform pipeline. The generated JSON files are regenerable. No F006–F010 files are touched, so no rollback needed there.
