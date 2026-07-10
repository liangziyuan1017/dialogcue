# Plan: Seamless Incremental Append of 2 New Records

> Fix Issues 1–4 (incremental tree, no orphaned/shifted rows, embeddings only for new
> sentences, keyword frequencies updated via upsert). Original 103 records stay intact;
> new content is appended at every stage. A pre-check gates on `call_id` uniqueness.

---

## 0. Current State (verified)

| Artifact | Count | Path |
|---|---|---|
| Raw input | 106 lines / 103 unique `call_id` (3 known dups) | `data/data_input/matched_data.jsonl` |
| `output_2 / logic / complete / merged` | 106 records each (resume-safe) | `data/data_output/` |
| `output_aligned.py` | 103 | `src/f001_schema_alignment/data/` |
| `output_rewarded.py` | 103 (deduped by `call_id`) | `src/f003_reward_labeling/data/` |
| `decision_tree.json` | 1384 nodes / 1701 sentences | `src/f004_decision_tree/data/` |
| `decision_tree_scored.json` | scored tree (no embeddings stored) | `src/f005_context_scoring/data/` |
| PostgreSQL | `nodes`, `sentences`, `taxonomy_keywords` (DSN in `.env`) | — |

**Tree node keys:** `state_id, branch_key, role, node_id, sentence_pool, children,
inherited_facts, inherited_emotions`. `path_signature` is **not** stored in the tree
JSON — it is computed during `score_tree()` and persisted only to the DB `nodes` table.

**Sentence keys (tree):** `script_id, script_text, source_call_ids, customer_willingness,
collector_action, fact_context` (+ optional `merged_from, gesture_type`).
**Sentence columns (DB):** `script_id, node_id, script_text, bg_bitmask_int, win_rate,
sas, bg_background, conversation_context, embedding` (+ generated `script_tsv`).

---

## 1. Critical Review — issues found in the existing code (must address before implementing)

These were discovered while verifying the plan against the actual tree/DB structure.
The incremental orchestrator must work around or fix them.

### CR-1. Both tree/DB orchestrators are currently BROKEN
`build_tree_and_db.py:63` and `build_and_score_tree.py:117` both call
`st.build_customer_info_lookup(rewarded)`, and `build_tree_and_db.py:68` calls
`st.score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup, embed_fn=embed_fn)`
(5 positional args). But the current `score_tree.py` (modified Jul 9, commit `4f43849`
custInfo migration) defines:
```python
def score_tree(tree, context_lookup, reward_lookup, conv_ctx_lookup=None, embed_fn=None)
```
and has **no** `build_customer_info_lookup`. Both orchestrators raise `AttributeError`
/ `TypeError` if run today. The existing scored tree was produced by `score_tree.py`'s
own `__main__` (`write_scored_tree()`), which uses the correct 4-arg API.

**Impact on plan:** The new incremental orchestrator (`add_records.py`) must call
`score_tree()` with the correct signature — `(tree, context_lookup, reward_lookup,
conv_ctx_lookup, embed_fn)` — mirroring `write_scored_tree()`, NOT the broken
`build_tree_and_db.run_score_tree`. Do not copy that code path.

### CR-2. `merge_dialogs` transform sequence mismatches `write_decision_tree`
- `write_decision_tree` (the function that built the current tree) runs:
  `_propagate_facts → _deduplicate_nodes → _prune_empty_subtrees →
  _consolidate_endpoints → _sort_keywords`.
- `merge_dialogs` runs: `_propagate_facts → _propagate_sentences →
  _prune_empty_subtrees → _consolidate_endpoints → _sort_keywords`
  (uses `_propagate_sentences`, **omits** `_deduplicate_nodes`).

**Impact:** Loading the existing tree (built with `_deduplicate_nodes`) and then
running `merge_dialogs` (which skips dedup) can leave duplicate nodes after adding
new records. **Fix:** align `merge_dialogs` to call the exact same sequence as
`write_decision_tree`.

### CR-3. `taxonomy_keywords` has no unique constraint on the natural key (VERIFIED in DB)
**Live DB state (queried):**
- Schema: `id int4 SERIAL PK`, `group_name text`, `category text`, `keyword text`,
  `frequency int4 DEFAULT 0`, `tsv tsvector`. Only unique index is `taxonomy_keywords_pkey`
  on `id` — **no unique constraint on `(group_name, category, keyword)`**.
- **36,544 rows for 6,907 distinct natural keys** — avg 5.3× duplication.
  4,836 keys have >1 row; max 12× (≈12 pipeline runs each re-inserted all keywords).
- **All duplicate rows have `frequency = 0`** — frequencies were never populated or
  updated (the `ON CONFLICT DO NOTHING` with no conflict target never fires, so every
  run inserts fresh rows with whatever frequency the source had, and it was 0).

`db.py:100` creates the table with only `id SERIAL PK`. The insert at
`build_tree_and_db.py:160` / `score_tree.py:250` uses `ON CONFLICT DO NOTHING`
with **no conflict target** — since no unique constraint exists on
`(group_name, category, keyword)`, the conflict never fires and **duplicate rows
accumulate on every run**. Frequencies are never updated.

**Impact — ordering is critical:**
1. **Dedup migration MUST run BEFORE the unique index is created** —
   `CREATE UNIQUE INDEX ... ON (group_name, category, keyword)` will **fail** while
   4,836 duplicate groups exist. Delete dups first (keep one row per natural key,
   `MAX(frequency)` — though all are currently 0, so any row suffices), then create
   the index.
2. After dedup: 36,544 → 6,907 rows. The `id int4` SERIAL will have gaps (normal,
   no sequence reset needed; 36,544 ≪ 2³¹ so no overflow concern).
3. Switch inserts to
   `ON CONFLICT (group_name, category, keyword) DO UPDATE SET frequency = EXCLUDED.frequency`
   so future runs update frequencies in place instead of appending duplicates.

### CR-4. `merge_dialogs` is already wired into `build_and_score_tree.py:106`
… but that orchestrator is broken (CR-1). The DB-populating path
(`build_tree_and_db.py:46`) always calls `write_decision_tree` (full rebuild).
So in practice, **no working incremental tree+DB path exists today**.

### CR-5. Embeddings are recomputed for ALL sentences every DB build
`build_tree_and_db.py:111-112` embeds every sentence text on each run. No cache.
The DB `sentences.embedding` column already holds valid vectors for existing
`script_id`s (text is immutable per `script_id`), so the DB itself is the natural
cache — we only need to embed **new** sentences.

---

## 2. Design Decisions (confirmed with user)

| Decision | Choice |
|---|---|
| New records location | Separate file `data/data_input/new_records.jsonl` |
| Cleaning depth | Full LLM cleaning chain (raw ASR → clean → logic → complete → merge) |
| Existing scores in affected nodes | **Recompute** `win_rate/sas/bg` for sentences in nodes that receive new content; freeze sentences in unaffected nodes |
| Original data | Never modified or deleted — in files and PostgreSQL. Keyword **frequencies** are the one intentional update (user requested). |

---

## 3. Phase-by-Phase Plan

### Phase 0 — Pre-check: `call_id` uniqueness gate

**New file: `src/check_new_records.py`**

1. Load existing `call_id` set from `output_rewarded.py` (canonical 103).
2. Load new records from `data/data_input/new_records.jsonl`.
3. **Fail (exit 1)** if any new `call_id`:
   - is in the existing set → "collides with old data",
   - is duplicated within the new batch → "duplicated in new batch",
   - is missing or empty.
4. Run `check_data_format.check_record()` on each new record for schema validity.
5. On success: print the new `call_id`s, exit 0.

The orchestrator calls this first and aborts on non-zero. This is the hard gate
the user requested.

---

### Phase 1 — Upstream incremental (append-only, minimal LLM)

#### 1a. Cleaning stages 1–3 — already append-safe (no code change)
Run `data_clean_2.py`, `data_logic.py`, `data_complete.py` with:
- `DATA_FILE = data/data_input/new_records.jsonl` (only 2 records visible)
- `OUTPUT_FILE = <existing output_2.py / output_logic.py / output_complete.py>`

Each loads existing output, skips the 103 existing `call_id`s, appends the 2 new,
checkpoints. Existing 103 rows untouched.

#### 1b. `data_merge` — temp combined source (no code change to data_merge)
`data_merge` reads source fields from `DATA_FILE` and **overwrites** `output_merged.py`.
If `DATA_FILE` = only `new_records.jsonl`, the 103 existing lose `custInfo`/etc.

**Fix:** Orchestrator creates a temp combined JSONL
(`matched_data.jsonl` + `new_records.jsonl`) in a temp dir, sets `DATA_FILE` = temp
combined for the `data_merge` step only. Existing 103 get identical fields
(deterministic re-attach), 2 new get theirs. `output_merged.py` overwritten but
content = old 103 (byte-identical fields) + 2 new appended.

#### 1c. f000 keyword discovery + turn labeling — label only new, recompute taxonomy
**Problem:** `discover_keywords` runs LLM on all records' turns → 103 redundant calls.

**New additive helper `label_new_records(new_records)` in `discover_keywords.py`**
(does not modify existing `discover_keywords`):
1. Load existing `output_labeled.py` (103 labeled records).
2. Load the 2 new records from `output_complete.py` (filter by new `call_id` set).
3. Run the **same batch-prompt LLM logic** (`_build_customer_batch_prompt`,
   `_build_collector_batch_prompt`) on **only the 2 new records' turns** → labels.
4. Append 2 new labeled records to existing 103 → write `output_labeled.py`.
5. **Recompute `state_keywords.json`** from the combined 105 labeled records:
   aggregate fact/emotion/action groups + frequencies (pure counting over existing
   groups). If the 2 new records introduce **brand-new keywords** not in existing
   groups, run **one** clustering LLM call (`_build_cluster_prompt`) to assign them
   — at most 1–2 calls, not 103.

Existing 103 labels are byte-identical (never re-processed).

#### 1d. Schema alignment + relabel — align only new (pure, no LLM)
`align_schema.align_record` and `relabel_state.relabel_record` are pure.
1. Load existing `output_aligned.py` (103).
2. Build `labeled_lookup` from `output_labeled.py` (now 105).
3. For each of the 2 new records: `align_record(r, labeled_lookup)` →
   `relabel_record(...)`.
4. Append 2 new aligned records to existing 103 → write `output_aligned.py`.

#### 1e. Reward labeling — label only new (LLM, per-record)
1. Load existing `output_rewarded.py` (103).
2. For each of the 2 new aligned records: `label_reward(r)` (1 LLM call each).
3. Append 2 new rewarded records to existing 103 → write `output_rewarded.py`.

**Net LLM cost for Phase 1:** ~2×3 cleaning + 2 f000 labeling + ≤2 clustering + 2
reward ≈ **~12 calls** (vs. 105+ if re-run naively).

---

### Phase 2 — Issue 1: Incremental tree build (no full rebuild)

**File: `src/f004_decision_tree/build_decision_tree.py`**

`merge_dialogs(tree_path, new_records, merge_decisions)` (line 386) already loads the
existing `decision_tree.json`, builds a registry from it, adds only the new records,
re-runs transforms, overwrites. This is the incremental path.

**Changes:**
1. **Fix CR-2:** align `merge_dialogs`'s transform sequence to match
   `write_decision_tree`:
   `_propagate_facts → _deduplicate_nodes → _prune_empty_subtrees →
   _consolidate_endpoints → _sort_keywords` (replace `_propagate_sentences` with
   `_deduplicate_nodes`).
2. **Add `write_dialog_records_incremental(new_records)`:** load existing
   `dialog_records.json`, append the 2 new call traces, overwrite. Existing 103
   traces untouched.
3. Orchestrator calls `merge_dialogs(TREE_PATH, new_2_rewarded, merge_cache)` with
   **only the 2 new records**. Existing nodes/branches preserved; new records add
   new branches/sentences. `_prune_empty_subtrees` cannot remove existing nodes
   (they only gain content). File overwritten but content = old tree + new branches.

**Why this fixes issue 1:** No `make_base_tree()` + full re-iteration. Existing tree
structure is loaded and extended, not regenerated from scratch.

---

### Phase 3 — Issue 2: Targeted DB upsert (no orphaned rows, recompute only affected nodes)

**File: `src/f007_infrastructure/db.py`** + orchestrator

After incremental tree build + score, identify three disjoint sets:

1. **New nodes** — `path_signature`s not already in `nodes` table → `INSERT` only.
2. **New sentences** — `script_id`s whose `source_call_ids` contain a new `call_id`
   → embed + `INSERT`.
3. **Affected existing nodes** — existing nodes whose `sentence_pool` now contains
   ≥1 new sentence → their existing sentences' `win_rate/sas/bg_bitmask_int/
   bg_background/conversation_context` recomputed (user chose "recompute affected
   node scores"). `script_text` and `embedding` are **not** touched (text immutable).

**New additive methods in `db.py`:**
- `get_existing_path_signatures() -> set[str]` — `SELECT path_signature FROM nodes`.
- `get_existing_script_ids() -> set[str]` — `SELECT script_id FROM sentences`.
- `update_sentence_scores(rows)` — `UPDATE sentences SET win_rate=%s, sas=%s,
  bg_bitmask_int=%s, bg_background=%s, conversation_context=%s WHERE script_id=%s`
  (no embedding, no text).
- Reuse existing `upsert_nodes` / `upsert_sentences` for new rows.

**Orchestrator logic:**
1. Score the incremental tree via `score_tree(tree, context_lookup, reward_lookup,
   conv_ctx_lookup, embed_fn=None)` — **correct 4-arg API** (CR-1). Scoring is cheap
   (no embedding unless DB-bound; embeddings handled separately in Phase 4).
2. Collect all nodes + sentences from the scored tree
   (`_collect_tree_nodes`, `_collect_tree_sentences`).
3. Query DB for existing `path_signatures` and `script_id`s.
4. **Nodes:** `new_nodes = [n for n if n.path_signature not in existing_sigs]` →
   `upsert_nodes(new_nodes)`. Existing node rows **never touched**.
5. **Sentences:**
   - `new_sentences = [s for s if s.script_id not in existing_ids]` →
     embed (Phase 4) + `upsert_sentences`.
   - `affected_existing = [s for s if s.script_id in existing_ids and s in an
     affected node]` → `update_sentence_scores` (score columns only).
   - Sentences in **unaffected nodes**: skipped → DB rows frozen. ✅
6. No `DELETE` ever issued → no orphaned rows, no data loss.

**How "affected node" is detected:** a node is affected if any sentence in its
`sentence_pool` has a new `call_id` in `source_call_ids`. Collect those nodes'
`path_signature`s; any existing sentence whose node's signature is in that set is
"affected existing".

**Why this fixes issue 2:** No global re-upsert. Existing rows are either frozen
(unaffected) or score-only-updated (affected). No `path_signature` shifts reach the
DB because the incremental tree preserves existing node structure (Phase 2). No
orphans created.

---

### Phase 4 — Issue 3: Embed only new sentences (DB as embedding cache)

**File: orchestrator** (no `embeddings.py` change)

**Problem:** `build_tree_and_db.py:111` calls `embed_texts(texts)` on **all**
sentences every run (CR-5).

**Fix:** In the incremental path, call `embed_texts()` **only on `new_sentences`'
texts** (a handful). Existing sentences' embeddings already live in the DB and their
`script_text` is immutable → embeddings still valid. The DB `sentences.embedding`
column **is the cache**.

- `affected_existing` sentences (score update only): embedding untouched.
- `new_sentences`: embed + insert.
- `decision_tree_scored.json` never stores embeddings (popped before write) → no
  cache concern there.

**Result:** Embedding calls drop from ~1701 to ~new sentences only. ✅

---

### Phase 5 — Issue 4: `taxonomy_keywords` upsert with frequency update

**File: `src/f007_infrastructure/db.py`**

**Verified DB state:** `id int4 SERIAL PK`, 36,544 rows / 6,907 distinct natural
keys, 4,836 duplicated groups (max 12×), all dup `frequency = 0`. No unique
constraint on `(group_name, category, keyword)`.

**Changes — strict ordering (dedup BEFORE index, else index creation fails):**
1. **One-time migration `dedup_taxonomy_keywords()`** (run once, before first
   incremental add):
   ```sql
   DELETE FROM taxonomy_keywords a USING taxonomy_keywords b
   WHERE a.group_name=b.group_name AND a.category=b.category
     AND a.keyword=b.keyword AND a.id > b.id;
   ```
   Keeps the lowest-`id` row per natural key (all dups have `frequency=0` so any
   row is equivalent). Result: 36,544 → 6,907 rows. `id int4` SERIAL retains gaps
   (normal, no sequence reset; 36,544 ≪ 2³¹). Idempotent — safe to re-run.
2. **Then** in `create_tables()`, add (additive, after dedup so it succeeds):
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS uq_taxonomy_keyword
   ON taxonomy_keywords (group_name, category, keyword);
   ```
3. **New method `upsert_taxonomy_keywords(rows)`:**
   ```sql
   INSERT INTO taxonomy_keywords (group_name, category, keyword, frequency)
   VALUES (%s, %s, %s, %s)
   ON CONFLICT (group_name, category, keyword) DO UPDATE SET frequency = EXCLUDED.frequency;
   ```
4. Replace inline `ON CONFLICT DO NOTHING` loops in `build_tree_and_db.py:158` and
   `score_tree.py:250` with `db.upsert_taxonomy_keywords(kw_rows)`.

**Why this fixes issue 4:** Frequencies updated in place (user requested). No
duplicates. Existing keyword rows updated, not duplicated. This is the **one
intentional modification to existing data** — frequency counts — which the user
explicitly requested.

---

### Phase 6 — Orchestrator + verification

**New file: `src/add_records.py`** — single entrypoint for incremental adds.

```
python3 src/add_records.py --new-input data/data_input/new_records.jsonl [--dsn ...]
```

**Execution order:**
1. **Phase 0:** `check_new_records.py` — abort on any `call_id` collision/dup. ← hard gate
2. **Phase 5 (pre):** `dedup_taxonomy_keywords()` — collapse 36,544→6,907 rows
   (one-time, idempotent). **Must run before the unique index is created.**
3. **Phase 1a:** cleaning stages 1–3 on new file (append to existing outputs).
4. **Phase 1b:** `data_merge` with temp combined source JSONL.
5. **Phase 1c:** `label_new_records()` (f000) — label 2 new, recompute taxonomy.
6. **Phase 1d:** align + relabel 2 new → append to `output_aligned.py`.
7. **Phase 1e:** reward-label 2 new → append to `output_rewarded.py`.
8. **Phase 2:** `merge_dialogs(TREE_PATH, new_2_rewarded, merge_cache)` →
   incremental tree. `write_dialog_records_incremental`.
9. **Phase 3+4:** score tree (correct 4-arg API) → query existing DB sigs/ids →
   insert new nodes → embed+insert new sentences → update scores in affected nodes.
10. **Phase 5:** `upsert_taxonomy_keywords` with updated frequencies.
11. Print summary: new `call_id`s, new node count, new sentence count, affected
    node count, embedding calls made.

**Verification (read-only, no mutation):**
- `output_rewarded.py` count == 105; first 103 `call_id`s unchanged (diff vs backup).
- `decision_tree.json`: load before/after → assert all old node `path_signature`s
  still present (superset check).
- DB: `SELECT count(*) FROM sentences` increased by exactly the new sentences;
  `SELECT count(*) FROM nodes` increased or equal; no existing `script_id` deleted.
- DB: `SELECT group_name, category, keyword, count(*) FROM taxonomy_keywords
  GROUP BY 1,2,3 HAVING count(*)>1` returns zero rows.
- DB: `SELECT count(*) FROM taxonomy_keywords` == 6,907 (post-dedup) + any new
  keywords from the 2 records.
- Spot-check 2 new `call_id`s present in `sentences` via
  `script_id LIKE '<new_call_id>_%'`.

---

## 4. Files Touched

| File | Change | New? |
|---|---|---|
| `src/check_new_records.py` | Pre-check gate (Phase 0) | **new** |
| `src/add_records.py` | Incremental orchestrator (Phase 6) | **new** |
| `src/f000_keyword_discovery/discover_keywords.py` | Add `label_new_records()` helper (additive) | modify |
| `src/f004_decision_tree/build_decision_tree.py` | Fix `merge_dialogs` transforms (CR-2); add `write_dialog_records_incremental` | modify |
| `src/f007_infrastructure/db.py` | Add `dedup_taxonomy_keywords()` migration (run before index); add unique index on `(group_name, category, keyword)` (CR-3); add `upsert_taxonomy_keywords`, `get_existing_path_signatures`, `get_existing_script_ids`, `update_sentence_scores` | modify |
| `src/f005_context_scoring/score_tree.py` | Replace inline keyword `ON CONFLICT DO NOTHING` (line 250) with `db.upsert_taxonomy_keywords` | modify |

**Not modified (surgical scope, Karpathy §3):**
- `src/build_tree_and_db.py` — broken (CR-1), unused; keyword fix deferred to CR-1
  follow-up. Touching a broken file adds risk for no benefit.
- Cleaning scripts, `align_schema`, `relabel_state`, `reward_label`,
  `embeddings.py` — called in incremental mode by the orchestrator without
  modifying their internals.

---

## 5. Review against SCBGE_GUIDELINE.md + ADRs + Karpathy guidelines

### 5a. Alignment confirmed (plan matches architecture)
- **ADR-029 (Additive Tree Building, Accepted):** `merge_dialogs(tree_path,
  new_records)` is the **architecture-intended incremental path** — "Incremental =
  merge only new call_ids; full rebuild = delete tree file + merge all." Phase 2
  uses exactly this. ✅
- **ADR-029:** the global post-transform chain (`_split_composite_nodes`,
  `_merge_sibling_facts`, `_collapse_redundant_facts`, `_split_by_action`) was
  **superseded and removed**. The tree is built additively; `_deduplicate_nodes`
  is "kept as a final pass for safety." Phase 2's CR-2 (add `_deduplicate_nodes`
  to `merge_dialogs`) aligns with this. ✅
- **ADR-024 / guideline §1.6:** embeddings are "persisted to PostgreSQL only;
  `decision_tree_scored.json` strips vectors before dump." Phase 4 (DB as cache,
  embed only new sentences) matches this exactly. ✅
- **ADR-021:** node identity = `(inherited_facts, inherited_emotions, branch_key)`;
  `node_id` = SHA-256 of identity. The tree is a **DAG** (a node can have multiple
  parents). `path_signature` is walk-derived, so a shared DAG node can produce
  multiple `nodes` rows (one per path). Phase 3 detects "affected" by
  `path_signature` (any path under a node that gained a new sentence) — correct
  for the DB's path-signature-keyed model. ✅
- **Karpathy §4 (Goal-Driven):** verification section defines checkable success
  criteria. ✅

### 5b. Corrections applied from this review
- **Risk Register fixed:** the prior draft listed "`_split_composite_nodes` /
  `_merge_sibling_facts` restructuring existing nodes" as a risk. **That risk is
  non-existent** — ADR-029 superseded and removed those transforms. The tree is
  purely additive; new records can only add branches/sentences, never restructure
  existing nodes. This makes the plan **safer** than previously stated.
- **Doc-drift noted:** SCBGE guideline §1.5 says "309 nodes, 782 sentences";
  the **actual verified tree is 1384 nodes / 1701 sentences**. The guideline is
  stale. Plan uses actual counts throughout.
- **Surgical scope narrowed (Karpathy §3):** `build_tree_and_db.py` is broken
  (CR-1) and unused. Per "touch only what you must," the plan now **does NOT
  modify `build_tree_and_db.py`** — only `score_tree.py:250` (the working
  `write_scored_tree` path) gets the keyword-upsert fix. The broken orchestrator
  is left untouched (deferred to the CR-1 follow-up).
- **File-size constraint (Karpathy §Code Standards):** `add_records.py` must stay
  under the 350-line hard limit. The orchestrator delegates to existing module
  functions (cleaning, `merge_dialogs`, `score_tree`, DB methods) rather than
  inlining logic, to stay lean.

---

## 6. Risk Register (revised)

| Risk | Mitigation |
|---|---|
| New records shift existing node `path_signature`s | **Cannot happen.** ADR-029 removed all restructuring transforms (`_split_composite_nodes`, `_merge_sibling_facts`, `_collapse_redundant_facts`, `_split_by_action`). The tree is purely additive — `merge_dialogs` only adds branches/sentences to the loaded tree. Existing `path_signature`s are stable. |
| `_deduplicate_nodes` (added to `merge_dialogs` per CR-2) merges an existing node | Merges by identity `(inherited_facts, inherited_emotions, branch_key)`. Existing nodes already deduped by the prior `write_decision_tree` run → re-running is a no-op on them. Only genuinely new duplicate-identity nodes (from the 2 new records) merge. ADR-021 confirms this is the intended safety net. |
| DAG shared node (multiple parents) → new sentence appears under multiple `path_signature`s | Correct behavior: the DB flattens the DAG into path-signature-keyed rows. Phase 3 inserts the new sentence under each path_signature it appears under (via `_collect_tree_sentences` which walks all paths). Existing sentences in those paths get score updates. No data loss. |
| `data_merge` temp combined file grows large over many incremental adds | Temp file is recreated fresh each run from `matched_data.jsonl` + current new batch; it does not accumulate. |
| DB connection pool exhaustion during embedding | Embedding only new sentences (a handful) — negligible load. |
| Orphaned `nodes`/`sentences` rows from a prior broken run | Out of scope (pre-existing). Separate cleanup script can be added later. |

---

## 7. Open question (non-blocking)
The existing `build_tree_and_db.py` and `build_and_score_tree.py` are broken (CR-1:
they call the removed `build_customer_info_lookup` and pass the wrong arity to
`score_tree`). This plan works around them by using the correct `score_tree` API in
the new orchestrator and does **not** modify either broken script (Karpathy §3:
surgical scope). A separate fix to bring those two scripts up to date is recommended
but **not required** for the incremental add to work. Flag for follow-up.
