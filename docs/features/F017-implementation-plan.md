# F017: Corpus Scalability Hardening — Implementation Plan

**Feature:** F017 — `docs/features/F017-corpus-scalability-hardening.md`
**Goal:** Pipeline runs end-to-end on 100k dialogs without OOM (peak RSS < 2 GiB)
**Acceptance Criteria:**
- [ ] No `_load_py_results` / importlib exec of `results = [...]` remains in `src/` (excl. tests)
- [ ] Pipeline runs end-to-end on a 100k-record synthetic corpus without OOM (peak RSS < 2 GiB)
- [ ] `add_records` incremental append is O(new batch), not O(corpus)
- [ ] DB upserts use `executemany`/`COPY`; no per-row `execute` loops in upsert paths
- [ ] `server.py` boot does not hold the full scored tree in `app.state`; node/label lookup served from DB
- [ ] `source_call_ids` stored in `sentence_sources` table; merge is O(new) not O(k²)
- [ ] Existing F000–F016 tests still pass

**Architecture:** Coordinate transform from O(corpus) in-memory full materialization to O(batch_size) streaming/DB-backed access. 8 independent tracks decomposed into 12 tasks across 5 phases.
**Tech Stack:** Python, PostgreSQL, asyncpg (runtime), psycopg2 (build-time), JSONL

**Decisions:** ADR-043 (JSONL streaming), ADR-044 (DB-served indexes), ADR-045 (sentence_sources join table)

---

## Phase 1: Foundation — JSONL Streaming (Track 1)

### Task 1: Create `load_jsonl` utility + migration script

**Files:**
- Create: `src/scripts/convert_py_to_jsonl.py`
- Create: `src/f007_infrastructure/jsonl_utils.py`
- Test: `src/tests/f007_infrastructure/test_jsonl_utils.py`

**Step 1: Write failing test** — test `load_jsonl` reads a JSONL file and returns `list[dict]` matching the `.py` literal API
**Step 2: Run test to verify it fails** — module doesn't exist
**Step 3: Write minimal implementation** — `load_jsonl(path) -> list[dict]` reading line-by-line; `write_jsonl(path, records)` appending JSON lines; `convert_py_to_jsonl.py` reads `.py` literal via existing `_load_py_results`, writes `.jsonl`
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): add jsonl_utils + convert_py_to_jsonl migration script`

### Task 2: Replace `_load_py_results` in pipeline modules

**Files:**
- Modify: `src/whole_pipeline.py:51` (remove `_load_py_results`, import `load_jsonl`)
- Modify: `src/build_tree_and_db.py:22` (same)
- Modify: `src/run_append.py:33` (same)
- Modify: `src/f005_context_scoring/build_and_score_tree.py:17` (same)
- Modify: `src/add_records.py:12` (update import, change callers at lines 54, 56, 99, 120)
- Test: `src/tests/test_whole_pipeline.py` (verify JSONL paths work)

**Step 1: Write failing test** — test that pipeline modules load `.jsonl` files, not `.py` files
**Step 2: Run test to verify it fails** — modules still call `_load_py_results`
**Step 3: Write minimal implementation** — replace each `_load_py_results(path)` call with `load_jsonl(path.with_suffix('.jsonl'))`; remove `_load_py_results` and `_write_py_results` definitions; update `add_records.py` append to use `write_jsonl` append mode
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): replace _load_py_results with load_jsonl in pipeline modules`

### Task 3: Replace importlib exec in discovery modules

**Files:**
- Modify: `src/f000_keyword_discovery/discover_keywords.py:22-29` (`_load_labeled_records` → `load_jsonl`)
- Modify: `src/f000_keyword_discovery/load_data.py:5-10` (`load_records` → `load_jsonl`)
- Test: `src/tests/f000_keyword_discovery/test_discover_keywords.py`

**Step 1: Write failing test** — test that discovery loads from `.jsonl`, not importlib exec
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — replace importlib exec with `load_jsonl` call pointing to `output_labeled.jsonl`
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): replace importlib exec with load_jsonl in discovery modules`

### Task 4: Run migration on existing data files

**Files:**
- Run: `python3 src/scripts/convert_py_to_jsonl.py` (converts 3 `.py` files to `.jsonl`)
- Delete: `src/f000_keyword_discovery/data/output_labeled.py`
- Delete: `src/f001_schema_alignment/data/output_aligned.py`
- Delete: `src/f003_reward_labeling/data/output_rewarded.py`

**Step 1: Run migration script** — converts `.py` literals to `.jsonl`
**Step 2: Verify output** — diff `load_jsonl(x.jsonl)` vs old `_load_py_results(x.py)` — must be identical
**Step 3: Delete old `.py` files**
**Step 4: Run full test suite** — all F000–F016 tests pass with JSONL
**Step 5: Commit** — `feat(F017): migrate .py literal data files to JSONL`

---

## Phase 2: Quick Wins (Tracks 6, 7)

### Task 5: Drop `copy.deepcopy` in discover_keywords (Track 6)

**Files:**
- Modify: `src/f000_keyword_discovery/discover_keywords.py:181` (`labeled_records = copy.deepcopy(records)` → `labeled_records = records`)
- Modify: `src/f000_keyword_discovery/discover_keywords.py:155` (`labeled_new = copy.deepcopy(new_records)` → `labeled_new = new_records`)
- Test: `src/tests/f000_keyword_discovery/test_discover_keywords.py`

**Step 1: Write failing test** — test that `discover_keywords` does not call `copy.deepcopy` (assert no deepcopy import usage, or test that records are labeled in place)
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — label in place; remove `import copy` if no other uses
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): drop copy.deepcopy in discover_keywords, label in place`

### Task 6: Replace `_is_ancestor` recursion with parent-pointer (Track 7)

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py:124-130` (replace recursive `_is_ancestor` with `_is_ancestor_parentptr`)
- Modify: `src/f004_decision_tree/build_decision_tree.py:86,149,455` (add `_parent` pointer on node creation)
- Test: `src/tests/f004_decision_tree/test_build_decision_tree.py`

**Step 1: Write failing test** — test `_is_ancestor` via parent-pointer returns same results as recursive version on a known tree
**Step 2: Run test to verify it fails** — parent-pointer doesn't exist
**Step 3: Write minimal implementation** — add `_parent` ref on each node at creation; `_is_ancestor_parentptr(node, target)` walks up parent chain (O(depth) worst case, but depth << subtree size)
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): replace _is_ancestor recursion with parent-pointer walk`

---

## Phase 3: Schema + DB (Tracks 3, 4, 5)

### Task 7: Create `sentence_sources` join table (Track 3)

**Files:**
- Modify: `src/f007_infrastructure/db.py` (add `CREATE TABLE sentence_sources` migration)
- Modify: `src/f007_infrastructure/async_db.py` (add async methods for sentence_sources)
- Test: `src/tests/f007_infrastructure/test_sentence_sources.py`

**Step 1: Write failing test** — test `sentence_sources` table exists with `(script_id, call_id)` PK; test insert + lookup
**Step 2: Run test to verify it fails** — table doesn't exist
**Step 3: Write minimal implementation** — add migration in `db.py` init; add `add_source_call_id(script_id, call_id)`, `get_source_call_ids(script_id)`, `has_source_call_id(script_id, call_id)` methods in both `db.py` and `async_db.py`
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): add sentence_sources join table schema + methods`

### Task 8: Replace `source_call_ids` list with DB queries (Track 3)

**Files:**
- Modify: `src/f004_decision_tree/build_decision_tree.py:113-116` (replace list membership+append with DB query)
- Modify: `src/f004_decision_tree/build_decision_tree.py:86,149,455` (replace `source_call_ids` list init with DB insert)
- Modify: `src/f004_decision_tree/merge_collector.py:195` (update reference)
- Modify: `src/f004_decision_tree/tree_transforms.py:9,491-492` (update references)
- Test: `src/tests/f004_decisiontree/test_build_decision_tree.py`

**Step 1: Write failing test** — test that merge uses `sentence_sources` table, not in-memory list; test O(new) merge behavior
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — `_place_sentence` calls `has_source_call_id` + `add_source_call_id` instead of list `in` + `append`; remove `.sort()` call
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): replace source_call_ids list with sentence_sources DB queries`

### Task 9: Batch DB writes with `executemany` (Track 4)

**Files:**
- Modify: `src/f007_infrastructure/db.py:148-149,180-181,221-222,263-265` (replace per-row `execute` loops with `executemany`)
- Modify: `src/f007_infrastructure/async_db.py:56-57,174-176` (replace per-row `await conn.execute` with `executemany`)
- Test: `src/tests/f007_infrastructure/test_db_batch.py`

**Step 1: Write failing test** — test that `upsert_nodes`, `upsert_sentences`, `upsert_taxonomy_keywords`, `update_sentence_scores` use `executemany` (batch insert)
**Step 2: Run test to verify it fails** — still per-row execute
**Step 3: Write minimal implementation** — use `cur.executemany(sql, batch_values)` for each upsert method; for async, use `await conn.executemany(sql, batch_values)`
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): batch DB upserts with executemany`

### Task 10: Stream full-table reads (Track 5)

**Files:**
- Modify: `src/f007_infrastructure/db.py:159-163` (`get_existing_path_signatures` — replace `fetchall` with server-side cursor / `EXISTS` query)
- Modify: `src/f007_infrastructure/db.py:167-171` (`get_existing_script_ids` — replace `fetchall` with named cursor / streaming)
- Test: `src/tests/f007_infrastructure/test_db_stream.py`

**Step 1: Write failing test** — test that `get_existing_script_ids` and `get_existing_path_signatures` use server-side cursors (or `yield` generator), not `fetchall`
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — use `psycopg2.extras.NamedTupleCursor` with `itersize` or switch to `SELECT EXISTS` for membership checks; for set operations, use server-side cursor with batch fetch
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): stream full-table reads with server-side cursors`

---

## Phase 4: Streaming Turn Labeling (Track 8)

### Task 11: Stream turn labeling — lazy iteration

**Files:**
- Modify: `src/f000_keyword_discovery/discover_keywords.py:33-43` (`_label_turns` — yield turns lazily instead of materializing `customer_turns`/`collector_turns` lists)
- Modify: `src/f000_keyword_discovery/discover_keywords.py:100-121` (`_recompute_taxonomy` — iterate records lazily)
- Modify: `src/f003_reward_labeling/analyze_customer_turns.py` (accept generator/iterator)
- Modify: `src/f003_reward_labeling/analyze_collector_turns.py` (accept generator/iterator)
- Modify: `src/f003_reward_labeling/define_willingness_levels.py` (accept generator/iterator)
- Test: `src/tests/f000_keyword_discovery/test_discover_keywords.py`

**Step 1: Write failing test** — test that `_label_turns` returns an iterator/generator, not a materialized list; test memory bounded
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — convert `_label_turns` to generator yielding `(turn, context)` tuples; downstream functions iterate lazily; `_recompute_taxonomy` iterates records without building intermediate lists
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): stream turn labeling with lazy iteration`

---

## Phase 5: Server — DB-Served Indexes (Track 2)

### Task 12: Serve indexes from DB instead of app.state

**Files:**
- Modify: `src/f009_api_server/server.py:174-176` (remove `app.state.tree/index/label_set_index` materialization)
- Modify: `src/f009_api_server/server.py:294-296,519-521` (replace `tree=`/`index=`/`label_set_index=` kwargs with DB query calls)
- Modify: `src/f006_retrieval_engine/retrieval_engine.py` (query DB for node/label lookup instead of reading from in-memory tree)
- Test: `src/tests/f009_api_server/test_server.py`

**Step 1: Write failing test** — test that server boot does not set `app.state.tree`; test that node lookup queries DB via `AsyncSentenceDB`
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation** — remove tree/index/label_set_index from `app.state`; add async DB query methods for node-by-path, label-set lookup; `retrieval_engine` calls these methods; **measure latency** — if > 10ms per lookup, add LRU cache
**Step 4: Run test to verify it passes**
**Step 5: Commit** — `feat(F017): serve scored tree indexes from DB, remove app.state materialization`

---

## Verification Checkpoints

| After Phase | Check |
|-------------|-------|
| Phase 1 | No `_load_py_results` / importlib exec remains; all tests pass with JSONL |
| Phase 2 | No `copy.deepcopy` in discover_keywords; no recursive `_is_ancestor`; all tests pass |
| Phase 3 | `sentence_sources` table exists; upserts use `executemany`; no `fetchall` in upsert paths; all tests pass |
| Phase 4 | Turn labeling uses generators; peak memory during labeling is O(batch) not O(corpus) |
| Phase 5 | `app.state.tree` is None; node lookup via DB query; latency < 10ms per lookup; all tests pass |
| Final | 100k synthetic corpus end-to-end run, peak RSS < 2 GiB; all F000–F016 tests pass |

## Synthetic Corpus Test

**Files:**
- Create: `src/scripts/generate_synthetic_corpus.py` — generates 100k synthetic dialog records for OOM testing
- Test: `src/tests/test_f017_scalability.py` — runs pipeline on synthetic corpus, asserts peak RSS < 2 GiB

**Note:** This is a verification step, not a delivery batch. Run after all 12 tasks complete.
