---
id: F017
name: Corpus Scalability Hardening (100k dialogs)
status: draft
owner: agent
related_features: [F000, F001, F003, F004, F005, F006, F007, F009, F015]
topics: [scalability, memory, streaming, database, performance]
doc_kind: spec
created: 2026-07-15
updated: 2026-07-15
---

# F017: Corpus Scalability Hardening (100k dialogs)

> **Status**: draft | **Owner**: agent | **Priority**: P1
>
> **Trigger**: `scoring_metrics.py:185` OOM (1.96 GiB) on a larger corpus; audit
> found systemic full-corpus in-memory patterns that break at 100,000 dialogs.

## Why

The pipeline was built for ~100 records. Every stage loads the entire corpus into
RAM via Python-literal `.py` files (`results = [...]` exec'd through importlib),
builds call_id-keyed dicts holding full turn lists, and holds the scored tree +
indexes in `app.state` for the process lifetime. At 100k dialogs these are
multi-GB allocations and O(k²) merge costs. A first manifestation already caused
a 1.96 GiB OOM in the SAS tfidf dense matrix (fixed in F005 via scipy.sparse);
this feature addresses the remaining systemic risks.

## What

Eight remediation tracks, ordered by leverage:

1. **Replace `.py` literal result files with streaming JSONL/SQLite** — eliminate
   every `_load_py_results` / importlib exec of `results = [...]`. (C1/C2)
2. **Move served indexes into the DB** — stop holding scored tree + node index +
   label-set index in `app.state` forever; serve from DB queries. (C3)
3. **Cap/hash `source_call_ids`** — store as a `sentence_sources` table or counted
   ref, not an unbounded list; fixes O(k²) merge. (H1/M1)
4. **Batch DB writes** — `executemany`/`COPY` for node/sentence/taxonomy upserts.
   (H3)
5. **Stream full-table reads** — server-side cursors / `EXISTS` for
   `get_existing_script_ids`, `query_db_state`. (H4)
6. **Drop `copy.deepcopy(records)`** in discover_keywords; label in place or
   stream. (H5)
7. **Replace `_is_ancestor` recursion** with parent-pointer/ancestor-set check.
   (H2)
8. **Stream turn labeling** — iterate records lazily instead of materializing
   ~2M turns into `all_turns`. (H6)

## Risk Inventory (audit output)

### Critical — OOM/stall at 100k
| ID | file:line | pattern |
|----|-----------|---------|
| C1 | `whole_pipeline.py:124`, `build_and_score_tree.py:43`, `score_tree.py:30/33`, `align_schema.py:21`, `reward_label.py:14`, `build_decision_tree.py:49`, `discover_keywords.py:22`, `add_records.py:54/99/120`, `check_new_records.py:10` | Full-corpus load via `.py` literal exec |
| C2 | `score_tree.py:67` (turns_lookup w/ full turn lists), `align_schema.py:28`, `add_records.py:60` | Full-corpus call_id dicts |
| C3 | `server.py:166-169`, `retrieval_engine.py:23/45/59` | Scored tree + indexes resident in app.state for lifetime |

### High — O(n²) / severe degradation
| ID | file:line | pattern |
|----|-----------|---------|
| H1 | `build_decision_tree.py:102-121` | `source_call_ids` list membership+append O(k²) |
| H2 | `build_decision_tree.py:123-129` | `_is_ancestor` recursive subtree scan per placement |
| H3 | `db.py:148/180/221/263`, `async_db.py:56/174` | Per-row execute loops (~1M INSERTs) |
| H4 | `db.py:167-173`, `cleanup_db.py:91-95` | Full-table fetchall into Python sets |
| H5 | `discover_keywords.py:181` | `copy.deepcopy(records)` of entire corpus |
| H6 | `discover_keywords.py:32-43`, `analyze_customer_turns.py:101`, `analyze_collector_turns.py:85`, `define_willingness_levels.py:65` | Materialize ~2M turns into all_turns |

### Medium
| ID | file:line | pattern |
|----|-----------|---------|
| M1 | `tree_transforms.py:163/183/236/266/333/358/381/431/445`, `build_decision_tree.py:167` | Whole-tree transforms per build/merge |
| M2 | `scoring_metrics.py:166/182` | Char n-grams w/o text truncation; dense df array |
| M3 | `build_decision_tree.py:478-504` | merge_decisions.json full read+rewrite per build |
| M4 | `check_data_format.py:134` | `f.readlines()` loads entire JSONL |
| M5 | `add_records.py:225` | O(existing × new) substring orphan scan |

### Already scalable (no action)
- pgvector HNSW for embedding similarity (`db.py:94`, `async_db.py:99`)
- SAS pool capped `POOL_CAP=50`; `_extract_cache` LRU 512; `SessionStore` TTL-capped
- F005 tfidf dense matrix → scipy.sparse (done 2026-07-15)

## Progress (2026-07-15)

| Item | Status | Detail |
|------|--------|--------|
| F005 SAS tfidf dense → `scipy.sparse` CSR | done | `scoring_metrics.py` — removed `np.zeros((n_docs, vocab))` OOM; `scipy>=1.11` added to `pyproject.toml` |
| Embed+insert streaming (batch=10) | done | `build_tree_and_db.py`, `add_records.py` — embed 10 → upsert 10 → repeat; bounds peak embedding memory to ~10 sentences instead of full corpus; orphan check hoisted before any write |
| F008 `merge_state` idempotency bug | done | `state_extraction.py:403-414` — non-winner new facts/emotions were silently dropped; now absorbed into `inherited_facts`/`inherited_emotions` per docstring contract; co-occurring emotions absorbed when facts win |
| Track 1 (replace `.py` literal loaders) | pending | — |
| Track 2 (serve indexes from DB) | pending | — |
| Track 3 (`source_call_ids` table) | pending | — |
| Track 4 (`execute_values` batch writes in `db.py`) | pending | embed+insert interleaving done; DB-level `execute_values` batching not yet applied |
| Track 5 (stream full-table reads) | pending | — |
| Track 6 (drop `copy.deepcopy`) | pending | — |
| Track 7 (`_is_ancestor` → parent pointer) | pending | — |
| Track 8 (stream turn labeling) | pending | — |

## Success Criteria

- [ ] No `_load_py_results` / importlib exec of `results = [...]` remains in `src/` (excl. tests)
- [ ] Pipeline runs end-to-end on a 100k-record synthetic corpus without OOM (peak RSS < 2 GiB)
- [ ] `add_records` incremental append is O(new batch), not O(corpus)
- [ ] DB upserts use `executemany`/`COPY`; no per-row `execute` loops in upsert paths
- [ ] `server.py` boot does not hold the full scored tree in `app.state`; node/label lookup served from DB
- [ ] `source_call_ids` stored in a separate table; merge is O(new) not O(k²)
- [ ] Existing F000–F016 tests still pass

## Files Touched (indicative)

| File | Track |
|------|-------|
| `src/whole_pipeline.py`, `src/add_records.py`, `src/check_new_records.py` | 1 |
| `src/f00{0,1,3,4,5}*/` loaders | 1 |
| `src/f009_api_server/server.py`, `src/f006_retrieval_engine/retrieval_engine.py` | 2 |
| `src/f004_decision_tree/build_decision_tree.py`, `tree_transforms.py` | 3, 7 |
| `src/f007_infrastructure/db.py`, `async_db.py` | 4, 5 |
| `src/f000_keyword_discovery/discover_keywords.py` | 6, 8 |
| `src/f003_reward_labeling/analyze_*.py`, `define_willingness_levels.py` | 8 |

## Out of Scope

- F005 SAS tfidf dense-matrix fix (already done via scipy.sparse)
- Embedding ANN (already pgvector HNSW)
- LLM call cost reduction (separate concern)
