# Debt Collection Call Data Pipeline

A six-stage LLM pipeline for cleaning and correcting ASR-transcribed debt collection call records from China Merchants Bank (招商银行). Powered by DeepSeek.

## Data

- **35 call records** between collectors (催收员) and overdue customers (客户)
- Source: `matched_data.jsonl` — one JSON object per line
- Each record contains: `call_id`, `dialog`, `call_date`, `cust_no`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info`
- Dialogs are ASR-transcribed with common errors: homophones, garbled text, fragmented turns, missing interjections

## Pipeline

```
matched_data.jsonl
    │
    ▼  (llm) data_clean_2.py     Emotion-preserving rewrite
    └── output_2.py
            │
            ▼  (llm) data_logic.py       催收员 logic repair
            └── output_logic.py
                    │
                    ▼  (llm) data_complete.py   Dialogue reconstruction
                    └── output_complete.py
                            │
                            ▼  (llm) data_polish.py     Long-turn splitting & customer reply inference
                            └── output_polish.py
                                    │
                                    ▼  (llm) data_alert.py      ASR error auditing
                                    └── output_alert.py
                                            │
                                            ▼  (llm) data_merge.py       Merge source fields (no LLM)
                                            └── output_merge.py
```

### Stage 1: Emotion-Preserving Rewrite — `(llm) data_clean_2.py`

Single-pass LLM rewrite that preserves emotional authenticity while removing ASR noise.

- **Keeps:** Emotionally meaningful disfluency (stutters, hesitations, emotional repetitions, incomplete sentences)
- **Removes:** Meaningless ASR noise (garbled fragments, repeated filler words with no semantic content)
- **Distinguishes:** `我……我是真的一下子拿不出来` (KEEP) vs `就是说就是说就是说……` (REMOVE)
- **Input:** `matched_data.jsonl` → **Output:** `output_2.py`

### Stage 2: 催收员 Logic Repair — `(llm) data_logic.py`

Targets **催收员 turns only**, leaving 客户 turns untouched.

- **Aggressively repairs:** Corrupted ASR phrases, malformed numbers, broken wording, semantically broken spans, duplicated garbage tokens
- **Preserves:** Customer turns exactly as-is, spoken-language style, emotional pacing, hesitation/fillers
- **Input:** `output_2.py` → **Output:** `output_logic.py`

### Stage 3: Dialogue Reconstruction — `(llm) data_complete.py`

Dialogue-level reconstruction beyond sentence-level repair — fixes conversational flow.

- **May:** Merge fragmented turns, split wrongly merged turns, reorder misplaced turns, rewrite corrupted spans, infer omitted transitions, insert missing replies, remove duplicated garbage
- **Should:** Reduce unnatural consecutive 催收员 monologues, restore back-and-forth rhythm, infer customer reactions, reconstruct hidden adjacency pairs
- **Must preserve:** Original intent, repayment negotiation logic, emotional pressure, hesitation, spoken-language style
- **Input:** `output_logic.py` → **Output:** `output_complete.py`

### Stage 4: Long-Turn Polishing — `(llm) data_polish.py`

Splits 催收员 turns exceeding 100 Chinese characters and inserts inferred short customer replies.

- **Triggers:** Questions, acknowledgments, topic shifts, interruption markers, persuasion pivots, repetition, naming, conjunction restarts, silence fill
- **Recursive:** If a split fragment still exceeds 100 chars, re-splits up to depth 3
- **Inserted turns:** 2–15 Chinese characters, marked with `"label": "1"`
- **Input:** `output_complete.py` → **Output:** `output_polish.py`

### Stage 5: ASR Error Auditing — `(llm) data_alert.py`

Scans every turn for residual ASR errors and adds an `"alert"` field when found.

- **Checks:** Mixed number formats, garbled numbers, word-level ASR errors, semantic inconsistencies, truncated fragments
- **Does NOT flag:** Hesitations, fillers, emotional repetitions, natural spoken numbers, `<PERSON>` placeholders
- **Input:** `output_polish.py` → **Output:** `output_alert.py`

### Stage 6: Source Field Merge — `(llm) data_merge.py`

Merges extra fields from `matched_data.jsonl` into the pipeline output (no LLM call).

- **Fields merged:** `call_date`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info`
- **Matches by:** `(call_id, cust_no)`
- **Input:** `matched_data.jsonl` + `output_alert.py` → **Output:** `output_merge.py`

### Stage 6: manual checks — `output_manual.py`
- manually check all alerts and corrected
- deleted irrelevant records: ai pick ups, death cases

## Generated Turn Tracking

Turns inserted or reconstructed by Stages 3–4 are marked with `"label": "1"` to distinguish them from original ASR turns.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai python-dotenv
```

Set `DEEPSEEK_API_KEY` in `.env`.

## Usage

### Run individual stages

```bash
source .venv/bin/activate

python "(llm) data_clean_2.py"      # Stage 1
python "(llm) data_logic.py"        # Stage 2
python "(llm) data_complete.py"     # Stage 3
python "(llm) data_polish.py"       # Stage 4
python "(llm) data_alert.py"        # Stage 5
python "(llm) data_merge.py"        # Stage 6
```

Each script skips already-processed records (resume-safe, checkpoint after each record).

### Run full pipeline with scheduling

```bash
python run_pipeline.py matched_data.jsonl
```

Runs all 6 stages sequentially, once per day, pausing during forbidden hours (4:00–5:00 AM). Checks every 600 seconds.

### Override input/output paths

```bash
DATA_FILE=input.py OUTPUT_FILE=output.py python "(llm) data_logic.py"
```

## ASR Error Types Addressed

| Type | Example |
|------|---------|
| Near-homophone | 诊端→前端, 寄收→催收, 刑专员→行专员 |
| Garbled/merged text | 标红即前转转→标红，即将转 |
| Number formatting | 1000千292→一千二百九十二, 102.钟→10点钟 |
| Role label bleed | text containing `催收员：` split into separate turns |
| Turn alignment | merge fragmented turns, insert missing short responses (嗯/好/对/是/知道了) |

## Design Principles

- **Progressive correction:** Six rounds — emotion preservation → 催收员 logic repair → dialogue reconstruction → long-turn polishing → error auditing → field merge — each building on the previous output
- **Emotion preservation:** Stutters, hesitations, emotional repetitions, and customer emotional expressions are intentionally preserved across all LLM stages
- **Asymmetric treatment:** 客户 turns are preserved as-is in logic repair; 催收员 turns are aggressively corrected for accuracy
- **Resume safety:** Each script checkpoints after every record and skips already-processed `call_id`s on restart
