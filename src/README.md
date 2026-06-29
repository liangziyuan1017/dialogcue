# src/

Source tree for the debt-collection call pipeline and retrieval/recommendation system.

## Orchestrator

| File | Description |
|------|-------------|
| `whole_pipeline.py` | **Pipeline orchestrator.** Runs all stages in sequence: clean → logic → complete → merge → keyword discovery → analysis → reward. Supports `--skip-llm`, `--merged-file`, and time-based scheduling (`--forbid-start`/`--forbid-end`/`--interval`). Phase-1 scripts (in `data/data_cleaning/`) are invoked as subprocesses with `PYTHONPATH=src/infra` so `llm_client`/`retry` resolve. Input from `data/data_input/`, outputs to `data/data_output/`. |

```bash
# Run from project root
python3 src/whole_pipeline.py                          # full pipeline, once
python3 src/whole_pipeline.py --skip-llm               # reuse existing merged output
python3 src/whole_pipeline.py --forbid-start 4         # daily, skip 4–5 AM
```

## data/ — Phase 1: LLM Cleaning

Phase-1 scripts and data live under `data/` (not `src/`):

| Path | Description |
|------|-------------|
| `data/data_input/matched_data.jsonl` | Source call records. |
| `data/data_cleaning/data_clean_2.py` | Step 1 — Emotion-preserving ASR rewrite. |
| `data/data_cleaning/data_logic.py` | Step 2 — Collector logic repair (customer turns untouched). |
| `data/data_cleaning/data_complete.py` | Step 3 — Dialogue reconstruction. |
| `data/data_cleaning/data_merge.py` | Step 4 — Source field merge (no LLM). |
| `data/data_output/output_*.py` | Phase-1 outputs (`output_2`, `output_logic`, `output_complete`, `output_merged`). |

See `data/README.md` for details.

## Feature Modules

Each module owns a `data/` subfolder holding the artifacts it produces. Cross-module reads reference the producer's `data/`. Shared reference data (`data/data_labels/`) stays under `data/`.

| Module | Feature | Code | `data/` artifacts (owned) |
|--------|---------|------|---------------------------|
| `f000_keyword_discovery/` | F000 | `discover_keywords.py`, `keyword_prompts.py`, `load_data.py` | `state_keywords.json`, `output_labeled.py` |
| `f001_schema_alignment/` | F001 | `align_schema.py` | `output_aligned.py` |
| `f003_reward_labeling/` | F003 | `analyze_collector_turns.py`, `analyze_customer_turns.py`, `reward_label.py`, `relabel_state.py`, `define_willingness_levels.py` | `output_rewarded.py`, `output_relabeled.py`, `collector_analysis.json`, `customer_analysis.json` |
| `f004_decision_tree/` | F004 | `build_decision_tree.py`, `merge_collector.py`, `tree_transforms.py`, `serve_tree.py`, `ui/` | `decision_tree.json`, `merge_decisions.json`, `dialog_records.json` |
| `f005_context_scoring/` | F005 | `build_and_score_tree.py`, `score_tree.py`, `scoring_metrics.py` | `decision_tree_scored.json` |
| `f006_retrieval_engine/` | F006 | `retrieval_engine.py`, `retrieval_ranking.py` | — (runtime: PostgreSQL) |
| `f007_infrastructure/` | F007 | `db.py`, `embeddings.py`, `llm_client.py`, `retry.py` | — |
| `f008_state_extraction/` | F008 | `state_extraction.py` | — |
| `f009_api_server/` | F009 | `server.py` | — |

> F007b (Vector Retrieval Integration) modifies f005/f006 in place — no own folder. F010 (API Mock + UI) is design-approved, not yet implemented.

**Cross-module data dependencies:**
- f001 reads `f000/data/output_labeled.py`
- f003 reads `f001/data/output_aligned.py` + `data/data_labels/*.csv`
- f004 reads `f003/data/output_rewarded.py`
- f005 reads `f004/data/decision_tree.json`, `f001/data/output_aligned.py`, `f003/data/output_rewarded.py`, `f000/data/state_keywords.json`, `data/data_output/{output_merged,collector_analysis,customer_analysis}`
- f006 reads `f005/data/decision_tree_scored.json`
- f008 reads `data/data_labels/*.csv`
- f009 reads `f000/data/state_keywords.json`, `f005/data/decision_tree_scored.json`

## f007_infrastructure/ — Shared Infrastructure (F007)

| File | Description |
|------|-------------|
| `llm_client.py` | DeepSeek client. `_get_client()`, `call_deepseek()`, `call_deepseek_json()`. Loads `DEEPSEEK_API_KEY` from `.env`. |
| `retry.py` | `retry_call()` wrapper for LLM calls. |
| `embeddings.py` | bge-m3 embedding client via Ollama (`embed_texts()`, `embed_single()`, 1024-dim). |
| `db.py` | `SentenceDB` — PostgreSQL + pgvector client. Tables: `nodes`, `sentences` (HNSW, tsvector, trigram), `taxonomy_keywords`. |

## f008_state_extraction/ — State Extraction (F008)

| File | Description |
|------|-------------|
| `state_extraction.py` | LLM-first state extraction (`extract_state`, `extract_state_llm`, `extract_state_keyword`), `merge_state` accumulation, `relabel_state`. |

## f009_api_server/ — API Server (F009)

| File | Description |
|------|-------------|
| `server.py` | FastAPI + Socket.IO server. `POST /recommend`: extract_state → merge_state → path lookup → vector search → fusion ranking → top-1. Socket.IO events: `start_session`, `customer_turn`, `collector_turn`, `end_session`. |

## tests/

Pytest suites mirroring the module layout (`tests/<module>/`). Run from project root:

```bash
python3 -m pytest src/tests/
```

## Setup

```bash
pip install -e .          # installs agent_tool package (pyproject.toml)
```

Set `DEEPSEEK_API_KEY` in `./.env` (project root). PostgreSQL + pgvector required for retrieval/API (see `f007_infrastructure/db.py`).
