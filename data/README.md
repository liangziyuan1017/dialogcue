# data/

Input data, pipeline outputs, and data-cleaning scripts for the debt-collection call processing pipeline.

## Layout

```
data/
├── data_input/        # source data
├── data_output/       # pipeline outputs (Phase 1–2)
├── data_cleaning/     # Phase-1 LLM cleaning scripts
└── data_labels/       # emotion/fact taxonomies
```

## data_input/

| File | Description |
|------|-------------|
| `matched_data.jsonl` | Source — 35 ASR-transcribed Mandarin debt-collection call records (one JSON object per line). Fields: `call_id`, `dialog`, `call_date`, `cust_no`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info`. |

## data_output/

Produced by `src/whole_pipeline.py` (run from project root). Phase-1 outputs are Python files containing `results = [...]`.

| File | Stage | Description |
|------|-------|-------------|
| `output_2.py` | 1 — data_clean_2 | Emotion-preserving ASR rewrite. |
| `output_logic.py` | 2 — data_logic | Collector (催收员) logic repair; customer turns untouched. |
| `output_complete.py` | 3 — data_complete | Dialogue reconstruction (merge/split/reorder turns, infer missing replies). |
| `output_merged.py` | 4 — data_merge | Source field merge (no LLM); matched by `(call_id, cust_no)`. |

Phase 2 analysis outputs (`collector_analysis.json`, `customer_analysis.json`) are written to `src/f003_reward_labeling/data/` (owned by the producer module). Phase 3 outputs (`output_aligned.py`, `output_rewarded.py`, `output_relabeled.py`) live under `src/f001_schema_alignment/data/` and `src/f003_reward_labeling/data/`.

## data_cleaning/

Phase-1 LLM cleaning scripts, invoked by `src/whole_pipeline.py` as subprocesses (`PYTHONPATH=src/infra` so `llm_client`/`retry` resolve).

| File | Description |
|------|-------------|
| `data_clean_2.py` | Step 1 — Emotion-preserving ASR rewrite. |
| `data_logic.py` | Step 2 — Collector logic repair (customer turns untouched). |
| `data_complete.py` | Step 3 — Dialogue reconstruction. |
| `data_merge.py` | Step 4 — Source field merge (no LLM). |

Each script resolves `INPUT_DIR = <root>/data/data_input`, `OUTPUT_DIR = <root>/data/data_output`, and loads `.env` from project root. Resume-safe: checkpoints after every record, skips processed `call_id`s. Defaults are used for standalone runs; `whole_pipeline.py` overrides via `DATA_FILE`/`OUTPUT_FILE` env vars.

## data_labels/

Manual and LLM-relabeled emotion/fact taxonomies used by state extraction (F008) and reward labeling (F003).

| File | Description |
|------|-------------|
| `emotions.csv`, `facts.csv` | Original emotion/fact label sets. |
| `emotions_relabeled.csv`, `facts_relabeled.csv` | LLM-relabeled variants. |
| `emotions_descriptions.py`, `facts_descriptions.py` | Label description for prompt context. |
| `facts_pipeline.csv` | Facts extracted via the pipeline run. |
| `llm_relabel_emotions.py`, `llm_relabel_facts.py` | Scripts that produce the relabeled CSVs. |
| `explore_distribution.ipynb` | Distribution exploration notebook. |
