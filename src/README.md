# Debt Collection Call Data Pipeline

A 7-stage pipeline for cleaning, reconstructing, and analyzing ASR-transcribed Mandarin debt-collection phone call records. Powered by DeepSeek.

## Data

- Call records between collectors (催收员) and overdue customers (客户)
- Source: `matched_data.jsonl` — one JSON object per line
- Each record contains: `call_id`, `dialog`, `call_date`, `cust_no`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info`
- Dialogs are ASR-transcribed with common errors: homophones, garbled text, fragmented turns, missing interjections

## Pipeline Overview

```
matched_data.jsonl
    │
    ▼  1. (llm) data_clean_2.py       Emotion-preserving ASR rewrite
    └── data_clean_2_output.py
            │
            ▼  2. (llm) data_logic.py         Collector logic repair
            └── data_logic_output.py
                    │
                    ▼  3. (llm) data_complete.py    Dialogue reconstruction
                    └── data_complete_output.py
                            │
                            ▼  4. (llm) data_merge.py      Merge source fields (no LLM)
                            └── data_merged_output.py
                                    │
                                    ▼  5. analyze_collector_turns    Collector behavior analysis
                                    └── collector_analysis.json
                                    │
                                    ▼  6. analyze_customer_turns     Customer fact/emotion analysis
                                    └── customer_analysis.json
                                    │
                                    ▼  7. align_schema + reward_label  Schema alignment & reward labeling
                                    └── output_aligned.py → output_rewarded.py
```

---

## File Descriptions

### LLM Cleaning Scripts (Phase 1)

| File | Description |
|------|-------------|
| `(llm) data_clean_2.py` | **Step 1 — Emotion-Preserving Rewrite.** Uses DeepSeek to clean ASR noise while preserving emotional authenticity. Keeps meaningful disfluency (hesitation, repetition, stutters) but removes garbage ASR artifacts. Input → `data_clean_2_output.py`. |
| `(llm) data_logic.py` | **Step 2 — Collector Logic Repair.** Targets only 催收员 (collector) turns. Fixes corrupted ASR phrases, malformed numbers, and broken semantics while preserving spoken customer-service tone. Customer turns are untouched. Input → `data_logic_output.py`. |
| `(llm) data_complete.py` | **Step 3 — Dialogue Reconstruction.** Fixes conversational flow at the dialogue level: merges/splits turns, reorders misplaced segments, infers missing short replies, and reconstructs broken adjacency pairs. Input → `data_complete_output.py`. |
| `(llm) data_merge.py` | **Step 4 — Source Field Merge.** No LLM call. Merges extra fields (`call_date`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info`) from `matched_data.jsonl` into the pipeline output, matched by `(call_id, cust_no)`. Input → `data_merged_output.py`. |

### Analysis Scripts (Phase 2)

| File | Description |
|------|-------------|
| `analyze_collector_turns.py` | **Step 5 — Collector Behavior Analysis.** Analyzes collector turns via DeepSeek and classifies them into action groups (greeting, information, plan_proposal, pressure, empathy, legal_threat, closure, etc.). Output → `collector_analysis.json`. |
| `analyze_customer_turns.py` | **Step 6 — Customer Turn Analysis.** Analyzes customer turns for facts (financial hardship, job loss, etc.), emotions (anxiety, anger, resignation, etc.), and willingness signals. Output → `customer_analysis.json`. |

### Reward & Alignment (Phase 3)

| File | Description |
|------|-------------|
| `align_schema.py` | **Step 7a — Schema Alignment.** Enriches pipeline records with structured context (credit rating, debt info, available plans, etc.) and per-turn `state` annotations from `output_labeled.py`. Output → `output_aligned.py`. |
| `reward_label.py` | **Step 7b — Reward Labeling.** Determines if a customer made a repayment commitment (R=1) or not (R=0). Provides explanation of the causal chain when a commitment is detected. Output → `output_rewarded.py`. |

### Shared Utilities

| File | Description |
|------|-------------|
| `llm_client.py` | Shared DeepSeek API client. Loads `DEEPSEEK_API_KEY` from `.env` via `python-dotenv`. Exports `_get_client()`, `call_deepseek()` (raw text) and `call_deepseek_json()` (parsed JSON response). Used by all LLM-dependent scripts. |
| `run_pipeline.py` | **Pipeline orchestrator.** Runs all 7 steps in sequence. Supports one-shot execution and time-based scheduling with configurable forbidden hours. |

### Data & Output Files

| File | Description |
|------|-------------|
| `matched_data.jsonl` | Source data — ASR-transcribed call records in JSONL format. |
| `output_labeled.py` | Per-turn state annotations (action, facts, emotions, willingness). Provides `state` fields merged into aligned output. |
| `output_manual.py` | Manual-curated merged output (equivalent to `data_merged_output.py`). Used by `align_schema.py` when run standalone. |
| `data_clean_2_output.py` | Output of Step 1 (Python file with `results = [...]`). |
| `data_logic_output.py` | Output of Step 2. |
| `data_complete_output.py` | Output of Step 3. |
| `data_merged_output.py` | Output of Step 4 — merged with source fields. |
| `collector_analysis.json` | Output of Step 5 — collector action groups. |
| `customer_analysis.json` | Output of Step 6 — customer facts, emotions, and willingness signals. |
| `output_aligned.py` | Output of Step 7a — records with structured context and state annotations. |
| `output_rewarded.py` | Output of Step 7b — records with reward (R=0/1) labels. |

---

## Setup

```bash
# Create virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install openai python-dotenv
```

Set your DeepSeek API key in `.env`:

```
DEEPSEEK_API_KEY=sk-your-key-here
```

All LLM scripts load the API key from `.env` via `llm_client.py` — no hardcoded keys.

---

## Usage

### Run the full pipeline (once)

```bash
# With API key from .env file
python3 run_pipeline.py

# Use a custom input file
python3 run_pipeline.py my_data.jsonl
```

### Run with scheduling (forbidden hours)

The pipeline runs once per day, skipping the specified time window:

```bash
# Don't run between 4:00–5:00 AM
python3 run_pipeline.py --forbid-start 4

# Don't run between 10:00 PM – 6:00 AM, check every 5 minutes
python3 run_pipeline.py --forbid-start 22 --forbid-end 6 --interval 300
```

### Re-run only analysis & reward (skip LLM cleaning)

```bash
python3 run_pipeline.py --skip-llm

# Use a specific merged file
python3 run_pipeline.py --skip-llm --merged-file data_merged_output.py
```

### Run individual steps manually

**Phase 1 — LLM Cleaning** (subprocess, resume-safe with `DATA_FILE` / `OUTPUT_FILE` env vars):

```bash
python3 "(llm) data_clean_2.py"                     # Step 1
python3 "(llm) data_logic.py"                       # Step 2
python3 "(llm) data_complete.py"                    # Step 3
python3 "(llm) data_merge.py"                       # Step 4
```

Override paths:

```bash
DATA_FILE=input.py OUTPUT_FILE=output.py python3 "(llm) data_logic.py"
```

**Phase 2 — Analysis** (in-process, reads from `data_merged_output.py`):

```bash
python3 -c "
import json, importlib.util as u
s = u.spec_from_file_location('m', 'data_merged_output.py')
m = u.module_from_spec(s); s.loader.exec_module(m)
import analyze_collector_turns as act
r = act.analyze_collector_turns(m.results)
json.dump(r, open('collector_analysis.json', 'w'), ensure_ascii=False, indent=2)
"                                                   # Step 5

python3 -c "
import json, importlib.util as u
s = u.spec_from_file_location('m', 'data_merged_output.py')
m = u.module_from_spec(s); s.loader.exec_module(m)
import analyze_customer_turns as acust
r = acust.analyze_customer_turns(m.results)
json.dump(r, open('customer_analysis.json', 'w'), ensure_ascii=False, indent=2)
"                                                   # Step 6
```

**Phase 3 — Schema Alignment & Reward Labeling**:

```bash
python3 align_schema.py                             # Step 7a
python3 reward_label.py                             # Step 7b
```

Each LLM cleaning script (Steps 1–4) is resume-safe — it skips already-processed `call_id`s and checkpoints after every record.

---

## Command-Line Reference

```
usage: run_pipeline.py [-h] [--skip-llm] [--merged-file MERGED_FILE]
                       [--forbid-start FORBID_START] [--forbid-end FORBID_END]
                       [--interval INTERVAL]
                       [input_file]

positional arguments:
  input_file            Input data file (default: matched_data.jsonl)

optional arguments:
  -h, --help            Show this help message
  --skip-llm            Skip Phase 1 (LLM cleaning) and use existing merged file
  --merged-file MERGED_FILE
                        Path to existing merged output (for --skip-llm)
  --forbid-start FORBID_START
                        Forbidden window start hour (0–23). Omit to run once.
  --forbid-end FORBID_END
                        Forbidden window end hour (default: forbid-start + 1)
  --interval INTERVAL   Scheduler check interval in seconds (default: 600)
```

---

## Technical Notes

- **Resume safety:** Each LLM cleaning script checkpoints after every record and skips already-processed `call_id`s on restart.
- **Inferred turns:** Step 3 may insert reconstructed customer replies — these are marked with `"label": "1"` to distinguish from original ASR turns.
- **Progressive correction:** Each LLM step builds on the previous output, with asymmetric treatment — collector turns are aggressively corrected while customer emotional texture is preserved.
- **State annotations:** Per-turn `state` fields (action, facts, emotions, willingness) come from `output_labeled.py`. Records not found in `output_labeled.py` will have turns without `state` fields.
- **API key management:** All LLM scripts use `llm_client._get_client()` which loads `DEEPSEEK_API_KEY` from `.env` via `python-dotenv`. No hardcoded API keys.
- **Scheduler:** When `--forbid-start` is set, the pipeline runs once per day outside the forbidden window. Omitting it runs the pipeline once and exits.

---

## Modifying Extra Fields

The source JSONL (`matched_data.jsonl`) contains these extra fields beyond `call_id`, `dialog`, and `cust_no`:

```
call_date, coll_user_id, mob_typ, talk_time, plan_evaluation, customer_info
```

If these field names change, or if you want to add/remove fields, here is exactly where to update:

### 1. Field list in `(llm) data_merge.py` (lines 14–20)

This defines which fields get merged into the final output. Add or remove field names here:

```python
EXTRA_FIELDS = [
    "call_date",
    "coll_user_id",
    "mob_typ",
    "talk_time",
    "plan_evaluation",
    "customer_info",
]
```

If a source key name is different (e.g. `call_date` is `callDate` in the JSONL), also check line 27 — the merge matches records by `(call_id, cust_no)` so confirm those keys match your source.

### 2. Record reader in `(llm) data_clean_2.py` (lines 166–170)

The initial data loader copies extra fields into intermediate records. Note the key renaming here:

```python
records.append({
    "call_id": record.get("call_id", ""),
    "dialog": turns,
    "calldate": record.get("call_date", ""),    # ← renamed: call_date → calldate
    "cust_no": record.get("cust_no", ""),        # ← renamed: cust_no → custno
    "colluserid": record.get("coll_user_id", ""),  # ← renamed: coll_user_id → colluserid
})
```

If a source field name changes, update the `record.get(...)` key. If the downstream key name matters, update the dict key.

### 3. Schema alignment in `align_schema.py` (lines 94–100)

The `align_record()` function reads fields from the merged records into the aligned output:

```python
return {
    "call_id": record["call_id"],
    "cust_no": record["cust_no"],
    "call_date": record.get("call_date", ""),        # line 97
    "coll_user_id": record.get("coll_user_id", ""),   # line 98
    "mob_typ": record.get("mob_typ", ""),             # line 99
    "talk_time": record.get("talk_time", ""),         # line 100
    "plan_evaluation": record.get("plan_evaluation", ""),  # line 101
    "customer_info": customer_info,                   # line 102
    ...
}
```

If a field was renamed in a previous step, update the `record.get(...)` key here.

### 4. `customer_info` sub-fields in `align_schema.py` (lines 63–74)

If the structure of `customer_info` changes (e.g. a Chinese key is renamed), update `build_context()`:

```python
def build_context(customer_info, mob_typ):
    return {
        "has_auto_loan": _parse_bool_has(customer_info.get("他行是否有车贷", ""), "有车贷")
        or _parse_bool_has(customer_info.get("我行是否有车贷", ""), "有车贷"),
        "has_mortgage": _parse_bool_has(customer_info.get("他行是否有房贷", ""), "有房贷")
        or _parse_bool_has(customer_info.get("我行是否有房贷", ""), "有房贷"),
        "credit_rating": _map_credit_rating(customer_info.get("24期缴款评等", "")),
        "days_delinquent": _map_days_delinquent(mob_typ),
        "total_debt": _parse_int(customer_info.get("总欠款", "0")),
        "external_debt": _parse_external_debt(customer_info.get("外部欠款金额", "")),
        "has_negotiation_history": customer_info.get("历史协商情况", "") != "无协商历史",
        "available_plans": _parse_available_plans(customer_info.get("当前可使用的协商方案", "")),
        "social_insurance_stable": "有社保" in customer_info.get("社保缴纳情况", "")
        and "灵活就业" not in customer_info.get("社保缴纳情况", ""),
    }
```

### 5. Reward cross-validation in `reward_label.py` (line 161)

The `cross_validate()` function reads `plan_evaluation` to verify reward consistency:

```python
plan_eval = rec.get("plan_evaluation", "")
```

If this field was renamed or removed, update this line accordingly.

### Summary table

| Change | File | Line(s) |
|--------|------|---------|
| Top-level field name in source JSONL | `(llm) data_merge.py` | 14–20 (`EXTRA_FIELDS`) |
| Source key for merge matching | `(llm) data_merge.py` | 25–27 (`load_source`) |
| Source field read + key rename | `(llm) data_clean_2.py` | 166–170 (`load_all_records`) |
| Field read in aligned output | `align_schema.py` | 94–102 (`align_record`) |
| `customer_info` sub-field keys | `align_schema.py` | 63–74 (`build_context`) |
| `plan_evaluation` in reward check | `reward_label.py` | 161 (`cross_validate`) |
