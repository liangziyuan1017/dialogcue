# Debt Collection Call Data Pipeline

A multi-stage data pipeline for parsing, cleaning, and correcting ASR-transcribed debt collection call records from China Merchants Bank (招商银行).

## Data Overview

- **31 call records** between collectors (催收员) and overdue customers (客户)
- Each record contains: `call_id`, `dialog`, `calldate`, `custno`, `colluserid`, `mobtyp`, `talktime`, `planevaluation`
- Dialogs are ASR-transcribed with common speech recognition errors (homophones, garbled text, fragmented turns)

## Pipeline Stages

```
data_0520.txt
    │
    ▼  data_parser.py  (parse raw text → structured JSON)
data_0520.json
    │
    ▼  (basic) data_clean.py  (rule-based cleaning)
(basic) data_0520.json
    │
    ├─── (llm) data_clean.py   (LLM two-pass correction — first record only)
    │          └── output.py
    │
    ├─── (llm) data_clean_1.py (LLM operations-based correction — first record only)
    │          └── output_1.py
    │
    └─── (llm) data_clean_2.py (LLM emotion-preserving rewrite — all 31 records)
               └── output_2.py
```

### Stage 1: Parse — `data_parser.py`

Converts raw text data into structured JSON with typed Python dataclasses.

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

### Stage 2: Basic Clean — `(basic) data_clean.py`

Rule-based cleaning that preserves original speech content.

1. **Fix truncated role labels** — `催收:` → `催收员:`
2. **Normalize punctuation** — Chinese → English (`，→,` `。→.` `？→?` `；→;` `：→:` etc.)
3. **Re-parse dialog** — re-segment with normalized separators
4. **Rebuild dialog_raw** — reconstruct from cleaned turns
5. **Clean planevaluation** — strip markdown artifacts (backticks, `---`, excess whitespace)
6. **Normalize planevaluation punctuation** — same CN→EN mapping
7. **Re-parse planevaluation** — extract structured fields from cleaned text

### Stage 3: LLM Correction — Three Approaches

#### 3a. Two-Pass Correction — `(llm) data_clean.py`

Original approach using DeepSeek V4 in two passes:

- **Pass 1:** Fix ASR transcription errors (homophones, garbled text, number formatting, role label bleed)
- **Pass 2:** Logical turn alignment (merge fragmented turns, insert missing short responses, reorder misplaced turns)
- **Safety net:** Programmatic regex-based known ASR fixes + role label splitting
- **Scope:** First record only
- **Output:** `output.py`

**Known issue:** LLM sometimes lists corrections in notes but doesn't apply them to the text.

#### 3b. Operations-Based Correction — `(llm) data_clean_1.py`

Improved architecture where the LLM outputs **operation lists** instead of full dialogs:

1. **Pre-processing** — normalize punctuation, fix known ASR patterns via regex, split role labels
2. **LLM Identify Structural Issues** — output list of `operations` (merge/insert/reorder) with indices
3. **Apply Structural Changes** — programmatically apply operations in order
4. **LLM Identify Remaining ASR Errors** — output list of `corrections` (index, from, to, reason)
5. **Apply ASR Corrections** — programmatically apply with validation
6. **Verify & Safety Net** — re-apply known patterns, validate conversational flow

**Advantages:**
- LLM outputs small lists, not entire dialogs (avoids token limits)
- Programmatic application ensures changes are actually made
- Validation step catches missed corrections
- Lower token usage and cost

**Scope:** First record only  
**Output:** `output_1.py`

#### 3c. Emotion-Preserving Rewrite — `(llm) data_clean_2.py`

Single-pass LLM approach that processes **all 31 records** while preserving emotional authenticity:

- **Keeps:** Emotionally meaningful disfluency (stutters, hesitations, emotional repetitions, incomplete sentences)
- **Removes:** Meaningless ASR noise (garbled fragments, repeated filler words with no semantic content)
- **Distinguishes:** "我……我是真的一下子拿不出来" (KEEP) vs "就是说就是说就是说……" (REMOVE)

**Scope:** All 31 records  
**Output:** `output_2.py`

## Files

| File | Description |
|------|-------------|
| `data_0520.txt` | Raw concatenated source data |
| `data_0520.json` | Parsed JSON (31 records) |
| `data_parser.py` | Parser, dataclasses, query functions |
| `(basic) data_clean.py` | Rule-based cleaning pipeline |
| `(basic) data_0520.json` | Cleaned JSON (CN→EN punctuation, fixed labels, no markdown artifacts) |
| `(llm) data_clean.py` | LLM two-pass correction (original approach, 1st record) |
| `(llm) data_clean_1.py` | LLM operations-based correction (improved approach, 1st record) |
| `(llm) data_clean_2.py` | LLM emotion-preserving rewrite (all 31 records) |
| `output.py` | LLM two-pass output for first record |
| `output_1.py` | LLM operations-based output for first record |
| `output_2.py` | LLM emotion-preserving output for all records |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai
```

## Usage

```bash
# Parse
python3 data_parser.py

# Basic clean
python3 "(basic) data_clean.py"

# LLM correction (requires DEEPSEEK_API_KEY)
export DEEPSEEK_API_KEY=your_key

# Original two-pass approach (1st record)
.venv/bin/python "(llm) data_clean.py"

# Operations-based approach (1st record)
.venv/bin/python "(llm) data_clean_1.py"

# Emotion-preserving rewrite (all 31 records)
.venv/bin/python "(llm) data_clean_2.py"
```

## ASR Error Types Addressed

- **Near-homophone errors** — 诊端→前端, 寄收→催收, 刑专员→行专员
- **Garbled/speech-merged text** — 标红即前转转→标红，即将转
- **Number formatting** — 1000千292→一千二百九十二, 102.钟→10点钟
- **Role label bleed** — text containing `催收员：` split into separate turns
- **Turn alignment** — merge fragmented turns, insert missing short responses (嗯/好/对/是/知道了/明白/噢/啊)
- **Markdown artifacts** — backticks, horizontal rules, excess whitespace in planevaluation

## Design Notes

- **Emotion preservation:** Stutters, hesitations (嗯, 呃, 唉), emotional repetitions (对对对, 好好好), and customer emotional expressions are intentionally preserved across all stages
- **Progressive correction:** Rule-based cleaning handles deterministic fixes; LLM handles context-dependent ASR errors
- **Validation:** Operations-based approach includes validation to ensure corrections are actually applied
