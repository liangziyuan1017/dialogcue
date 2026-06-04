# Debt Collection Call Data Pipeline

A multi-stage LLM pipeline for cleaning and correcting ASR-transcribed debt collection call records from China Merchants Bank (招商银行).

## Data Overview

- **31 call records** between collectors (催收员) and overdue customers (客户)
- Each record contains: `call_id`, `dialog`, `calldate`, `custno`, `colluserid`, `mobtyp`, `talktime`, `planevaluation`
- Dialogs are ASR-transcribed with common speech recognition errors (homophones, garbled text, fragmented turns)

## Pipeline Stages

```
data_0520.json
    │
    ▼  (llm) data_clean_2.py  (LLM emotion-preserving rewrite — all 31 records)
    └── output_2.py
            │
            ▼  (llm) data_logic.py  (LLM 催收员 logic repair — all 31 records)
            └── output_logic.py
                    │
                    ▼  (llm) data_complete.py  (LLM dialogue reconstruction — all 31 records)
                    └── output_complete.py
```

### Stage 0: Parse — `data_parser.py`

Loads structured JSON into typed Python dataclasses and provides query helpers.

| Class | Fields |
|-------|--------|
| `CallRecord` | call_id, dialog_raw, calldate, custno, colluserid, mobtyp, talktime, planevaluation_raw, turns, evaluation |
| `DialogTurn` | role, text |
| `PlanEvaluation` | reduction_plan, reduction_evidence, mina_plan, mina_evidence, technique, technique_evidence |

**Key functions:**
- `load_records()` — load JSON into `CallRecord` objects
- `parse_dialog()` — split dialog string into `DialogTurn` list
- `parse_planevaluation()` — extract evaluation fields from markdown table
- `filter_by_date()`, `filter_by_user()`, `search_dialog()` — query helpers
- `summary()` — aggregate statistics

### Stage 1: Emotion-Preserving Rewrite — `(llm) data_clean_2.py`

Single-pass LLM approach that processes **all 31 records** while preserving emotional authenticity:

- **Keeps:** Emotionally meaningful disfluency (stutters, hesitations, emotional repetitions, incomplete sentences)
- **Removes:** Meaningless ASR noise (garbled fragments, repeated filler words with no semantic content)
- **Distinguishes:** "我……我是真的一下子拿不出来" (KEEP) vs "就是说就是说就是说……" (REMOVE)

**Scope:** All 31 records  
**Output:** `output_2.py`

### Stage 2: 催收员 Logic Repair — `(llm) data_logic.py`

LLM correction that targets **催收员 turns only** while leaving 客户 turns untouched:

- **Goal:** Repair ASR corruption in collector speech so negotiation logic, financial terms, and amounts are accurate
- **Preserves:** Customer turns exactly as-is (no modification), spoken-language style, emotional pacing, hesitation/fillers
- **Aggressively repairs:** Corrupted ASR phrases, malformed numbers, broken wording, semantically broken spans, duplicated garbage tokens
- **Input:** `output_2.py` (emotion-preserved output)
- **Scope:** All 31 records
- **Output:** `output_logic.py`

### Stage 3: Dialogue Reconstruction — `(llm) data_complete.py`

Dialogue-level reconstruction that goes beyond sentence-level repair to fix conversational flow:

- **Goal:** Reconstruct the most likely natural conversation from corrupted ASR transcripts
- **May:** Merge fragmented turns, split wrongly merged turns, reorder misplaced turns, rewrite corrupted spans, infer omitted transitions, insert missing replies, remove duplicated garbage
- **Should:** Reduce unnatural consecutive 催收员 monologues, restore back-and-forth rhythm, infer customer reactions, reconstruct hidden adjacency pairs
- **Must preserve:** Original intent, repayment negotiation logic, emotional pressure, hesitation, spoken-language style
- **Generated turns:** Marked with `"label": "1"` to distinguish from original turns
- **Input:** `output_logic.py`
- **Scope:** All 31 records
- **Output:** `output_complete.py`

## Files

| File | Description |
|------|-------------|
| `data_0520.json` | Parsed JSON (31 records) |
| `data_parser.py` | Parser, dataclasses, query functions |
| `(llm) data_clean_2.py` | LLM emotion-preserving rewrite (all 31 records) |
| `output_2.py` | LLM emotion-preserving output for all records |
| `(llm) data_logic.py` | LLM 催收员 logic repair (all 31 records) |
| `output_logic.py` | LLM logic-repair output for all records |
| `(llm) data_complete.py` | LLM dialogue reconstruction (all 31 records) |
| `output_complete.py` | LLM dialogue reconstruction output for all records |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai
```

## Usage

```bash
# LLM correction (requires DEEPSEEK_API_KEY in .env)
source .venv/bin/activate

# Emotion-preserving rewrite (all 31 records)
python "(llm) data_clean_2.py"

# 催收员 logic repair (all 31 records)
python "(llm) data_logic.py"

# Dialogue reconstruction (all 31 records)
python "(llm) data_complete.py"
```

## ASR Error Types Addressed

- **Near-homophone errors** — 诊端→前端, 寄收→催收, 刑专员→行专员
- **Garbled/speech-merged text** — 标红即前转转→标红，即将转
- **Number formatting** — 1000千292→一千二百九十二, 102.钟→10点钟
- **Role label bleed** — text containing `催收员：` split into separate turns
- **Turn alignment** — merge fragmented turns, insert missing short responses (嗯/好/对/是/知道了/明白/噢/啊)

## Design Notes

- **Emotion preservation:** Stutters, hesitations (嗯, 呃, 唉), emotional repetitions (对对对, 好好好), and customer emotional expressions are intentionally preserved across all stages
- **Progressive correction:** Three LLM rounds — emotion preservation → 催收员 logic repair → full dialogue reconstruction — each building on the previous output
- **Asymmetric treatment:** 客户 turns are preserved as-is in logic repair; 催收员 turns are aggressively corrected for accuracy
- **Generated turn tracking:** Reconstructed/inserted turns are marked with `"label": "1"` for traceability
