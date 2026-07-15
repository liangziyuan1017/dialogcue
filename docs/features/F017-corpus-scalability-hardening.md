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
> **Trigger**: `scoring_metrics.py` OOM (1.96 GiB) on a larger corpus; audit
> found systemic full-corpus in-memory patterns that break at 100,000 dialogs.

## Why

The pipeline was built for ~100 records. Every stage loads the entire corpus into
RAM via Python-literal `.py` files (`results = [...]` exec'd through importlib),
builds call_id-keyed dicts holding full turn list, and holds the scored tree +
indexes in `app.state` for the process lifetime. At 100k dialogs these are
multi-GB allocations and O(k²) merge costs. A first manifestation already caused
a 1.96 GiB OOM in the SAS TF-IDF matrix (fixed in F005 via jieba word ngrams +
ref-vocabulary restriction, see ADR-041); this feature addresses the remaining
systemic risks.

## What

Eight remediation tracks, ordered by leverage:

1. **Replace `.py` literal result files with streaming JSONL/SQLite** — eliminate
   every `_load_py_results` / importlib exec of `results = [...]`. (C1/C2)
2. **Move served indexes into the DB** — stop holding scored tree + node index +
   label-set index in `app.state` forever; serve from DB queries. (C3)
3. **Cap/hash `source_call_ids`** — store as a `sentence_sources` join table
   `(script_id, call_id)`, not an unbounded list; fixes O(k²) merge. (H1/M1)
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
| ID | location | pattern |
|----|----------|---------|
| C1 | `whole_pipeline._load_py_results`, `build_and_score_tree._load_py_results`, `score_tree._load_py`, `align_schema`, `reward_label`, `build_decision_tree`, `discover_keywords`, `add_records._load_py_results`, `check_new_records`, `run_append._load_py_results` | Full-corpus load via `.py` literal exec |
| C2 | `score_tree.build_turns_lookup` (full turn lists), `align_schema`, `add_records` | Full-corpus call_id dicts |
| C3 | `server.py` startup (`app.state.tree/index/label_set_index`), `retrieval_engine` | Scored tree + indexes resident in app.state for lifetime |

### High — O(n²) / severe degradation
| ID | location | pattern |
|----|----------|---------|
| H1 | `build_decision_tree._place_sentence` | `source_call_ids` list membership+append O(k²) |
| H2 | `build_decision_tree._is_ancestor` | Recursive subtree scan per placement |
| H3 | `db.py` upsert methods, `async_db.py` upsert methods | Per-row execute loops (~1M INSERTs) |
| H4 | `db.py.get_existing_*`, `cleanup_db` | Full-table fetchall into Python sets |
| H5 | `discover_keywords.discover_keywords` | `copy.deepcopy(records)` of entire corpus |
| H6 | `discover_keywords`, `analyze_customer_turns`, `analyze_collector_turns`, `define_willingness_levels` | Materialize ~2M turns into all_turns |

### Medium
| ID | location | pattern |
|----|----------|---------|
| M1 | `tree_transforms` (multiple functions), `build_decision_tree._apply_transforms` | Whole-tree transforms per build/merge |
| M2 | ~~`scoring_metrics._char_ngrams`~~ | ~~Char n-grams w/o text truncation; dense df array~~ **Fixed** — see ADR-041 |
| M3 | `build_decision_tree._save_merge_decisions` | merge_decisions.json full read+rewrite per build |
| M4 | `check_data_format` | `f.readlines()` loads entire JSONL |
| M5 | `add_records._find_orphans` | O(existing × new) substring orphan scan |

### Already scalable (no action)
- pgvector HNSW for embedding similarity (`db.py`, `async_db.py`)
- SAS pool capped `POOL_CAP=50`; `_extract_cache` LRU 512; `SessionStore` TTL-capped
- F005 SAS OOM fixed: char bigrams → jieba word bigrams + ref-vocabulary restriction (ADR-041, 2026-07-15)
- F005 `embed_fn` removed from `score_tree.py` — embedding happens once in `build_tree_and_db.py`, eliminating double-embedding path (2026-07-15)

## Risk → Track Mapping

| Track | Resolves |
|-------|----------|
| 1 (JSONL/SQLite loaders) | C1, C2 |
| 2 (serve indexes from DB) | C3 |
| 3 (source_call_ids table) | H1, M1 |
| 4 (batch DB writes) | H3 |
| 5 (stream full-table reads) | H4 |
| 6 (drop deepcopy) | H5 |
| 7 (parent pointer) | H2 |
| 8 (stream turn labeling) | H6 |

## Progress (2026-07-15)

| Item | Status | Detail |
|------|--------|--------|
| F005 SAS OOM fix | done | `scoring_metrics.py` — replaced `_char_ngrams` with `_word_ngrams` (jieba), removed `_build_tfidf_matrix`, ref-vocabulary restriction makes TF-IDF matrix `(n_docs, \|ref_ngrams\|)` instead of `(n_docs, millions)`. See ADR-041 |
| F005 embed_fn removal | done | `score_tree.py` — removed `embed_fn` param from `_score_sentence_pool`/`score_tree`; embedding now happens once in `build_tree_and_db.py` (line 112), eliminating redundant double-embedding |
| Embed+insert streaming (batch=10) | done | `build_tree_and_db.py`, `add_records.py` — embed 10 → upsert 10 → repeat; bounds peak embedding memory to ~10 sentences instead of full corpus; orphan check hoisted before any write |
| F008 `merge_state` idempotency bug | done | `state_extraction.py` — non-winner new facts/emotions were silently dropped; now absorbed into `inherited_facts`/`inherited_emotions` per docstring contract; co-occurring emotions absorbed when facts win |
| Track 1 (replace `.py` literal loaders) | pending | Migration: one-time `convert_py_to_jsonl.py` script; downstream consumers change `_load_py_results(path)` → `load_jsonl(path)` returning same list[dict] API |
| Track 2 (serve indexes from DB) | pending | — |
| Track 3 (`source_call_ids` table) | pending | Schema: `CREATE TABLE sentence_sources (script_id TEXT, call_id TEXT, PRIMARY KEY (script_id, call_id))`; replaces `source_call_ids` list on sentence dicts |
| Track 4 (`execute_values` batch writes in `db.py`) | pending | embed+insert interleaving done; DB-level `execute_values` batching not yet applied |
| Track 5 (stream full-table reads) | pending | — |
| Track 6 (drop `copy.deepcopy`) | pending | 1-line change in `discover_keywords.py` — label in place |
| Track 7 (`_is_ancestor` → parent pointer) | pending | — |
| Track 8 (stream turn labeling) | pending | — |

## Memory Budget Estimate (100k dialogs)

| Component | Current (~105 records) | Projected (100k) | After F017 |
|-----------|----------------------|-------------------|------------|
| `.py` literal corpus (aligned+rewarded) | ~15 MB | ~1.5 GB | 0 (JSONL/SQLite) |
| `app.state` tree + indexes | ~2 MB | ~200 MB | 0 (served from DB) |
| SAS TF-IDF matrix (per pool) | ~KBs | ~KBs | ~KBs (ref-vocab-restricted) |
| Embedding vectors (1024-dim × N) | ~0.4 MB | ~400 MB | ~4 MB (batch=10) |
| jieba dictionary | ~50 MB | ~50 MB | ~50 MB |
| `turns_lookup` (all turns in RAM) | ~5 MB | ~500 MB | 0 (streamed) |
| **Peak RSS** | **~70 MB** | **~2.7 GB** | **< 2 GB** |

## Success Criteria

- [ ] No `_load_py_results` / importlib exec of `results = [...]` remains in `src/` (excl. tests)
- [ ] Pipeline runs end-to-end on a 100k-record synthetic corpus without OOM (peak RSS < 2 GiB)
- [ ] `add_records` incremental append is O(new batch), not O(corpus)
- [ ] DB upserts use `executemany`/`COPY`; no per-row `execute` loops in upsert paths
- [ ] `server.py` boot does not hold the full scored tree in `app.state`; node/label lookup served from DB
- [ ] `source_call_ids` stored in `sentence_sources` table; merge is O(new) not O(k²)
- [ ] Existing F000–F016 tests still pass

## Files Touched (indicative)

| File | Track |
|------|-------|
| `src/whole_pipeline.py`, `src/add_records.py`, `src/check_new_records.py`, `src/run_append.py` | 1 |
| `src/f00{0,1,3,4,5}*/` loaders | 1 |
| `src/scripts/convert_py_to_jsonl.py` (new) | 1 |
| `src/scripts/generate_synthetic_corpus.py` (new) | test infra |
| `src/f009_api_server/server.py`, `src/f006_retrieval_engine/retrieval_engine.py` | 2 |
| `src/f004_decision_tree/build_decision_tree.py`, `tree_transforms.py` | 3, 7 |
| `src/f007_infrastructure/db.py`, `async_db.py` | 4, 5 |
| `src/f000_keyword_discovery/discover_keywords.py` | 6, 8 |
| `src/f003_reward_labeling/analyze_*.py`, `define_willingness_levels.py` | 8 |

## Out of Scope

- F005 SAS OOM fix (already done — jieba word bigrams + ref-vocab restriction, ADR-041)
- F005 embed_fn removal (already done — embedding moved to build_tree_and_db.py)
- Embedding ANN (already pgvector HNSW)
- LLM call cost reduction (separate concern)
