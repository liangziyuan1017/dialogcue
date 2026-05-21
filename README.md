# Debt Collection Call Data Pipeline

Pipeline for parsing, cleaning, and correcting ASR-transcribed debt collection call records from China Merchants Bank (招商银行).

## Data Overview

- **31 call records** between collectors (催收员) and overdue customers (客户)
- Each record contains: `call_id`, `dialog`, `calldate`, `custno`, `colluserid`, `mobtyp`, `talktime`, `planevaluation`
- Dialogs are ASR-transcribed with common speech recognition errors

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
    ▼  (llm) data_clean.py  (LLM-based ASR correction)
output.py
```

### Stage 1: Parse — `data_parser.py`

Converts raw text data into structured JSON with typed Python dataclasses.

| Class | Fields |
|-------|--------|
| `CallRecord` | call_id, dialog_raw, calldate, custno, colluserid, mobtyp, talktime, planevaluation_raw, turns, evaluation |
| `DialogTurn` | role, text |
| `PlanEvaluation` | reduction_plan, reduction_evidence, mina_plan, mina_evidence, technique, technique_evidence |

Key functions:
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

### Stage 3: LLM Correction — `(llm) data_clean.py`

DeepSeek V4 corrects ASR transcription errors that rules cannot catch.

Corrections include:
- **Near-homophone errors** — 诊端→前端, 寄收→催收, 刑专员→行专员
- **Garbled/speech-merged text** — 标红即前转转→标红，即将转
- **Number formatting** — 1000千292→一千二百九十二, 102.钟→10点钟
- **Role label bleed** — text containing `催收员：` split into separate turns
- **Turn alignment** — merge fragmented turns, insert missing short responses

Preserved by design:
- Stutters, hesitations (嗯, 呃, 唉)
- Emotional repetitions (对对对, 好好好)
- Filler words and incomplete sentences
- Customer emotional expressions

Output format adds `source` (`original` / `ai-generated`) and `confidence` fields to each turn.

## Files

| File | Description |
|------|-------------|
| `data_0520.txt` | Raw concatenated source data |
| `data_0520.json` | Parsed JSON (31 records) |
| `data_parser.py` | Parser, dataclasses, query functions |
| `(basic) data_clean.py` | Rule-based cleaning pipeline |
| `(basic) data_0520.json` | Cleaned JSON (CN→EN punctuation, fixed labels, no markdown artifacts) |
| `(llm) data_clean.py` | LLM-based ASR correction via DeepSeek V4 |
| `output.py` | LLM-corrected output for first record |

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
.venv/bin/python "(llm) data_clean.py"
```
