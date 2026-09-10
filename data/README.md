# data/

Input data, pipeline outputs, and data-cleaning scripts for the debt-collection call processing pipeline.

## Layout

```
data/
├── data_input/        # source data
├── data_output/       # Phase-1 cleaning outputs (jsonl)
├── data_cleaning/     # Phase-1 LLM cleaning scripts
└── data_labels/       # canonical fact/emotion taxonomies + llm_relabel_*
```

## data_input/

| File | Description |
|------|-------------|
| `input_data.jsonl` | Source records (one JSON object per line). **Schema is exactly three fields:** `call_id` (string), `dialog` (string; turns separated by `；`/`;`), `custInfo` (JSON string or list of `{tagName, tagValue}`). Validate with `python3 src/check_data_format.py data/data_input/input_data.jsonl --strict`. |
| `new_data.jsonl` | Incremental input for `src/run_append.py` (F015). Same 3-field schema. On successful append, records are appended to `input_data.jsonl` and this file is cleared. |

## data_output/

Produced by `src/data_clean.py` (run from project root). All Phase-1 artifacts are **JSONL** (one record per line).

| File | Stage | Description |
|------|-------|-------------|
| `output_clean.jsonl` | 1 — data_clean | Emotion-preserving ASR rewrite. Passes through `call_id` / `dialog` / `custInfo`. |
| `output_logic.jsonl` | 2 — data_logic | Collector (催收员) logic repair; customer turns untouched. |
| `output_complete.jsonl` | 3 — data_complete | Dialogue reconstruction (merge/split/reorder turns, infer missing replies). |
| `output_merged.jsonl` | 4 — data_merge | Source field merge (no LLM); matched by `call_id` only. |

Downstream stages write under `src/`:

| File | Owner |
|------|-------|
| `src/f000_keyword_discovery/data/output_labeled.jsonl` | F000 (includes canonical relabel) |
| `src/f000_keyword_discovery/data/state_keywords.json` | F000 taxonomy |
| `src/f001_schema_alignment/data/output_aligned.jsonl` | F001 |
| `src/f003_reward_labeling/data/output_rewarded.jsonl` | F003 (dedup by `call_id`) |
| `src/f003_reward_labeling/data/collector_analysis.json`, `customer_analysis.json` | F003 aggregation from F000 |

> **Downstream guarantee (ADR-042):** the decision tree built from `output_rewarded.jsonl` enforces unique `script_id`s via `_dedup_script_ids_global` and forces end nodes to leaves (`_enforce_end_leaves`). Verify with `PYTHONPATH=src python3 -m f004_decision_tree.check_tree` (D4).

## data_cleaning/

Phase-1 LLM cleaning scripts, invoked by `src/data_clean.py` as subprocesses (`PYTHONPATH=src` so `f007_infrastructure.llm_client` / `retry` resolve).

| File | Description |
|------|-------------|
| `data_clean.py` | Step 1 — Emotion-preserving ASR rewrite. |
| `data_logic.py` | Step 2 — Collector logic repair (customer turns untouched). |
| `data_complete.py` | Step 3 — Dialogue reconstruction. |
| `data_merge.py` | Step 4 — Source field merge (no LLM); join key = `call_id`. |

Each script resolves `INPUT_DIR` / `OUTPUT_DIR` under `data/`, and loads `.env` from the project root. Resume-safe: checkpoints after every record, skips processed `call_id`s. `data_clean.py` (orchestrator) overrides paths via `DATA_FILE` / `OUTPUT_FILE` env vars.

## data_labels/

Canonical fact/emotion taxonomies used by F000 canonical relabel, F001 `relabel_state`, and F008 online extraction. Shared runtime: `src/f007_infrastructure/label_relabel.py` (reuses the `llm_relabel_*` modules below).

| File | Description |
|------|-------------|
| `emotions.csv`, `facts.csv` | Original emotion/fact label inventories. |
| `emotions_relabeled.csv`, `facts_relabeled.csv` | Cached tag → canonical category maps (grown by offline and online LLM relabel). |
| `emotions_descriptions.py`, `facts_descriptions.py` | Canonical `TAG_LABELS` (keys + domain + description) for prompts and hard-match. |
| `llm_relabel_emotions.py`, `llm_relabel_facts.py` | Relabel pipelines: `build_categories_block`, `classify_batch`, `validate_mapping`, `TAG_LABELS`. Imported at runtime by `label_relabel.py` — do not reimplement. |

**Cascade:** descriptions hard-match → CSV map → `llm_relabel_{facts,emotions}.classify_batch` → append new rows to `*_relabeled.csv`.
