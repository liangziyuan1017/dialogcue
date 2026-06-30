# src/ — Debt-Collection Pipeline & Retrieval System

Complete pipeline from raw call data to a scored decision tree, PostgreSQL database, and live UI.

---

## First-Time Setup

Follow these steps in order on a fresh machine.

### Step 1: Install PostgreSQL 16

```bash
# macOS
brew install postgresql@16
brew services start postgresql@16

# Ubuntu/Debian
sudo apt install postgresql-16 postgresql-16-dev
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

Create the database and required extensions:

```bash
createdb icbc
psql icbc -c "CREATE EXTENSION IF NOT EXISTS vector"   # pgvector
psql icbc -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"   # trigram search
```

> **pgvector** must be installed as a PostgreSQL extension. On macOS: `brew install pgvector`. On Ubuntu: see https://github.com/pgvector/pgvector#installation.

### Step 2: Install Ollama

```bash
# macOS
brew install ollama
ollama serve                    # start the daemon (or it auto-starts)

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the embedding model:

```bash
ollama pull bge-m3              # 1024-dim, ~2 GB download
```

Verify it's running:

```bash
curl http://localhost:11434/v1/models
```

### Step 3: Get a DeepSeek API Key

1. Go to https://platform.deepseek.com/
2. Sign up or log in
3. Navigate to **API Keys** → **Create new key**
4. Copy the key (starts with `sk-`)

You will need this key for all LLM-powered stages (data cleaning, keyword discovery, reward labeling, state extraction).

### Step 4: Install Python Dependencies

Requires **Python >=3.14, <3.15**.

```bash
# From project root
pip install -e .                # core: fastapi, uvicorn, openai, psycopg2-binary, pgvector, numpy, pyyaml, etc.
pip install -e ".[dev]"         # dev: pytest, aiofiles, cryptography
```

### Step 5: Create `.env` File

Create `.env` in the **project root** (parent of `src/`):

```bash
cat > .env << 'EOF'
DEEPSEEK_API_KEY=sk-your-key-here
PG_DSN=dbname=icbc user=postgres
EMBEDDING_MODEL=bge-m3
EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_DIM=1024
EOF
```

| Variable | Required by | Description |
|----------|-------------|-------------|
| `DEEPSEEK_API_KEY` | Stages 1–3, API server | DeepSeek LLM API key |
| `PG_DSN` | Stage 6, API server | PostgreSQL connection string |
| `EMBEDDING_MODEL` | Stages 5–6, API server | Ollama model name |
| `EMBEDDING_BASE_URL` | Stages 5–6, API server | Ollama OpenAI-compatible endpoint |
| `EMBEDDING_API_KEY` | Stages 5–6, API server | Ollama auth (default: `ollama`) |
| `EMBEDDING_DIM` | Stages 5–6, API server | Embedding vector dimension |

### Step 6: Verify Setup

```bash
# Check Python
python3 --version               # should be 3.14.x

# Check PostgreSQL
psql icbc -c "SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_trgm')"

# Check Ollama
ollama list                     # should show bge-m3

# Check DeepSeek (replace with your key — this makes a real API call)
python3 -c "from openai import OpenAI; c=OpenAI(api_key='sk-xxx'); print(c.chat.completions.create(model='deepseek-chat',messages=[{'role':'user','content':'hi'}],max_tokens=5).choices[0].message.content)"
```

### Step 7: Configuration

Runtime parameters live in `config.md` (YAML frontmatter). Key sections you may want to adjust:

| Section | What it controls | Key fields |
|---------|-----------------|------------|
| `llm` | LLM calls | `model`, `api_base`, `temperature` |
| `embedding` | Embedding model | `model`, `dimension`, `api_base` |
| `ranking_weights` | Sentence scoring fusion | `win_rate`, `vec_score`, `sas`, `bg_boost`, `bitmask_score` (must sum to 1.0) |
| `hnsw` | Vector index | `m`, `ef_construction` |
| `server` | UI ports | `tree_explorer_port` (default 8420) |
| `retry` | LLM retry policy | `max_retries`, `min_sleep`, `max_sleep` |

---

## Pipeline Stages

> All commands below assume you are in the **project root** (parent of `src/`).

### Stage 1: LLM Data Cleaning

**Input:** `data/data_input/matched_data.jsonl` (raw call records)

**Output:** `data/data_output/output_merged.py`

Runs 4 LLM-powered cleaning steps as subprocesses:

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `data/data_cleaning/data_clean_2.py` | Emotion-preserving ASR rewrite |
| 2 | `data/data_cleaning/data_logic.py` | Collector logic repair (customer turns untouched) |
| 3 | `data/data_cleaning/data_complete.py` | Dialogue reconstruction |
| 4 | `data/data_cleaning/data_merge.py` | Source field merge (no LLM) |

**Requires:** DeepSeek API key

```bash
python3 src/whole_pipeline.py data/data_input/matched_data.jsonl
```

To skip LLM cleaning and reuse existing merged output:

```bash
python3 src/whole_pipeline.py --skip-llm
python3 src/whole_pipeline.py --skip-llm --merged-file path/to/output_merged.py
```

### Stage 2: Keyword Discovery & Turn Labeling

**Input:** `data/data_output/output_merged.py`

**Output:** `src/f000_keyword_discovery/data/state_keywords.json`, `src/f000_keyword_discovery/data/output_labeled.py`

Discovers facts, emotions, collector actions, and willingness levels from the merged records.

**Requires:** DeepSeek API

This runs automatically as part of `whole_pipeline.py` (Phase 1.5).

### Stage 3: Analysis & Schema Alignment

**Input:** `output_labeled.py`, `output_merged.py`, `data/data_labels/*.csv`

**Output:**

- `src/f003_reward_labeling/data/collector_analysis.json`
- `src/f003_reward_labeling/data/customer_analysis.json`
- `src/f001_schema_alignment/data/output_aligned.py`
- `src/f003_reward_labeling/data/output_rewarded.py`
- `src/f003_reward_labeling/data/output_relabeled.py`

Runs collector/customer turn analysis, schema alignment, reward labeling, and state relabeling.

**Requires:** DeepSeek API, `data/data_labels/*.csv` (relabel maps)

This runs automatically as part of `whole_pipeline.py` (Phases 2–4).

### Stages 4–6: Build Tree → Score Tree → Populate Database

These three stages are run by a single command: `build_tree_and_db.py`.

| Stage | Input | Output | What it does |
|-------|-------|--------|--------------|
| 4 | `src/f003_reward_labeling/data/output_rewarded.py` | `src/f004_decision_tree/data/decision_tree.json` | Build decision tree: merge collector turns, split composite nodes, merge sibling facts, propagate, deduplicate |
| 5 | `src/f004_decision_tree/data/decision_tree.json`, `src/f001_schema_alignment/data/output_aligned.py`, `src/f003_reward_labeling/data/output_rewarded.py` | `src/f005_context_scoring/data/decision_tree_scored.json` | Score every sentence: bg_constraints, bitmask, win_rate (HWR), SAS, bg_background, conversation_context |
| 6 | `src/f005_context_scoring/data/decision_tree_scored.json`, `src/f001_schema_alignment/data/output_aligned.py`, `src/f000_keyword_discovery/data/state_keywords.json` | PostgreSQL tables `nodes`, `sentences`, `taxonomy_keywords` | Upsert nodes, sentences + embeddings (Ollama bge-m3), taxonomy keywords |

**Run stages 4–5 only** (no database, no Ollama needed):

```bash
python3 src/build_tree_and_db.py --skip-db
```

**Run stages 4–6** (requires PostgreSQL + pgvector and Ollama with bge-m3):

```bash
python3 src/build_tree_and_db.py
# or with custom DSN:
python3 src/build_tree_and_db.py --dsn "dbname=icbc user=postgres host=localhost"
```

### Stage 7: Launch UIs

**Requires:** `decision_tree_scored.json` (both UIs); PostgreSQL populated (API server only)

| UI | Port | URL |
|----|------|-----|
| Tree Explorer | 8420 | `http://localhost:8420/ui/tree_explorer.html` |
| API Server | 8000 | `http://localhost:8000/docs` (Swagger) |

```bash
# Both UIs:
python3 src/launch_ui.py

# Tree explorer only:
python3 src/launch_ui.py --tree-only

# API server only:
python3 src/launch_ui.py --api-only

# Don't auto-open browser:
python3 src/launch_ui.py --no-open
```

The API server exposes:
- `POST /recommend` — single-turn recommendation
- Socket.IO events: `start_session`, `customer_turn`, `collector_turn`, `end_session`

Press `Ctrl+C` to shut down all servers.

---

## Data Format Validation

Before running any pipeline stage, validate your input data:

```bash
python3 src/check_data_format.py data/data_input/matched_data.jsonl --strict
```

The checker validates two known record formats:

| Format | Records | Required keys | `customer_info` |
|--------|---------|---------------|-----------------|
| **Canonical** | Already processed | `call_id`, `dialog`, `call_date`, `cust_no`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info` | Dict with 11 always-present Chinese keys (总欠款, 学历, etc.) + 4 optional |
| **Raw API** | From upstream system | `call_id`, `dialog`, `cust_no` | `custInfo` — JSON string of `[{tagName, ...}]` pairs |

Checks performed:
- All records have `call_id` (non-empty string) and `dialog` (string)
- Canonical records: all 9 top-level keys present, `customer_info` has expected Chinese keys, `mob_typ` in valid set
- Raw records: `custInfo` parses as JSON list of `{tagName, ...}` dicts
- Duplicate `call_id` detection

Use `--strict` to exit with code 1 on any error (for CI/pre-commit hooks).

---

## Quick Start (Full Pipeline)

After completing **First-Time Setup** above:

```bash
# 0. Validate input data
python3 src/check_data_format.py data/data_input/matched_data.jsonl --strict

# 1. Run data pipeline (stages 1-3: clean → discover → align → reward → relabel)
python3 src/whole_pipeline.py data/data_input/matched_data.jsonl

# 2. Build tree + score + populate database (stages 4-6, single command)
python3 src/build_tree_and_db.py

# 3. Launch UIs (stage 7)
python3 src/launch_ui.py
```

To skip LLM cleaning if you already have merged output:

```bash
python3 src/whole_pipeline.py --skip-llm
python3 src/build_tree_and_db.py
python3 src/launch_ui.py
```

---

## Processing New Data on Top of Existing

When new call records arrive and you want to incorporate them without re-running the entire pipeline from scratch.

### Scenario A: New records only (no changes to existing data)

1. **Back up your existing merged output** (it will be overwritten):

   ```bash
   cp data/data_output/output_merged.py data/data_output/output_merged_existing.py
   ```

2. **Place the new data file** in `data/data_input/`:

   ```bash
   cp /path/to/new_data.jsonl data/data_input/new_data.jsonl
   ```

3. **Validate the new data**:

   ```bash
   python3 src/check_data_format.py data/data_input/new_data.jsonl --strict
   ```

4. **Run LLM cleaning on the new file only** (Stage 1):

   ```bash
   python3 src/whole_pipeline.py data/data_input/new_data.jsonl
   ```

   This overwrites `data/data_output/output_merged.py` with only the new records. It also overwrites the downstream outputs (`output_aligned.py`, `output_rewarded.py`, etc.) — that's expected; they'll be regenerated in step 6.

5. **Merge new records with existing merged output**:

   ```bash
   python3 -c "
   import importlib.util, json
   def load(path):
       spec = importlib.util.spec_from_file_location('m', path)
       mod = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(mod)
       return mod.results
   existing = load('data/data_output/output_merged_existing.py')
   new = load('data/data_output/output_merged.py')
   combined = existing + new
   with open('data/data_output/output_merged.py', 'w') as f:
       f.write('results = ')
       text = json.dumps(combined, ensure_ascii=False, indent=2)
       text = text.replace(': null', ': None').replace(': true', ': True').replace(': false', ': False')
       f.write(text)
       f.write('\n')
   print(f'Combined: {len(combined)} records ({len(existing)} existing + {len(new)} new)')
   "
   ```

6. **Re-run stages 2–6** on the combined data:

   ```bash
   python3 src/whole_pipeline.py --skip-llm     # stages 2-3
   python3 src/build_tree_and_db.py             # stages 4-6
   ```

7. **Restart the UIs** to pick up the new data:

   ```bash
   python3 src/launch_ui.py
   ```

### Scenario B: Incremental — skip cleaning, re-process from aligned output

If the new records have already been cleaned and merged (e.g. from a prior run), and you just need to rebuild the tree and database:

```bash
# Re-run analysis + reward + relabel on existing merged output (stages 2-3)
python3 src/whole_pipeline.py --skip-llm

# Rebuild tree, score, and repopulate database (stages 4-6)
python3 src/build_tree_and_db.py

# Restart UIs (stage 7)
python3 src/launch_ui.py
```

### Scenario C: Tree/database only — no new records, just re-score or re-index

If you changed `config.md` (ranking weights, HNSW params, etc.) but the data hasn't changed:

```bash
# Rebuild tree + score + repopulate database (stages 4-6, reads existing output_rewarded.py / output_aligned.py)
python3 src/build_tree_and_db.py

# Restart UIs (stage 7)
python3 src/launch_ui.py
```

### Important notes

- **Database upserts are idempotent** for nodes and sentences (`ON CONFLICT ... DO UPDATE`). Taxonomy keywords use `ON CONFLICT DO NOTHING`, so re-running won't update frequency values if they change — truncate first: `psql icbc -c "TRUNCATE taxonomy_keywords"`.
- **Merge decisions are cached** — `src/f004_decision_tree/data/merge_decisions.json` is read and written on each tree build. If you want to force re-merging, delete this file before running.
- **Embeddings are recomputed every time** — Stage 6 calls Ollama for all sentences. For large trees, this is the slowest step. There is no embedding cache.
- **The API server loads the scored tree on startup** — you must restart it after any data change. The `--reload` flag in uvicorn watches for code changes, not data file changes.
- **Relabel maps are required** — `data/data_labels/*.csv` must exist for stages 2–3 (f003 reward labeling and f008 state extraction). These are hand-curated and checked into the repo.

---

## Scheduling

Run the data pipeline daily, skipping forbidden hours (e.g. 4–5 AM to avoid rate limits). This only schedules stages 1–3; you still need to run `build_tree_and_db.py` and restart the UIs afterward:

```bash
python3 src/whole_pipeline.py --forbid-start 4 --forbid-end 5 --interval 600
# After the pipeline completes:
python3 src/build_tree_and_db.py
```

---

## Module Reference

| Module | Feature | Key Code | Data Artifacts |
|--------|---------|----------|----------------|
| Orchestrator | — | `whole_pipeline.py`, `build_tree_and_db.py`, `launch_ui.py`, `check_data_format.py` | — |
| `f000_keyword_discovery/` | F000 | `discover_keywords.py`, `load_data.py` | `state_keywords.json`, `output_labeled.py` |
| `f001_schema_alignment/` | F001 | `align_schema.py` | `output_aligned.py` |
| `f003_reward_labeling/` | F003 | `analyze_collector_turns.py`, `reward_label.py`, `relabel_state.py` | `output_rewarded.py`, `output_relabeled.py`, `collector_analysis.json`, `customer_analysis.json` |
| `f004_decision_tree/` | F004 | `build_decision_tree.py`, `merge_collector.py`, `tree_transforms.py` | `decision_tree.json`, `merge_decisions.json` |
| `f005_context_scoring/` | F005 | `score_tree.py`, `scoring_metrics.py` | `decision_tree_scored.json` |
| `f006_retrieval_engine/` | F006 | `retrieval_engine.py`, `retrieval_ranking.py` | — (runtime: PostgreSQL) |
| `f007_infrastructure/` | F007 | `db.py`, `embeddings.py`, `llm_client.py`, `retry.py`, `config.py` | — |
| `f008_state_extraction/` | F008 | `state_extraction.py` | — |
| `f009_api_server/` | F009 | `server.py` | — |

**Cross-module data flow:**

```
f000/output_labeled.py ──→ f001/align_schema.py
f001/output_aligned.py ──→ f003/reward_label.py ──→ f004/build_decision_tree.py
f004/decision_tree.json ──→ f005/score_tree.py ──→ f006/retrieval_engine.py
f005/decision_tree_scored.json ──→ f009/server.py
f000/state_keywords.json ──→ f009/server.py
```

---

## Tests

```bash
python3 -m pytest src/tests/            # all tests
python3 -m pytest src/tests/f005/       # specific module
```

Integration tests in `f005_context_scoring/` require `decision_tree_scored.json` to exist. Run `build_tree_and_db.py --skip-db` first if those tests fail.
