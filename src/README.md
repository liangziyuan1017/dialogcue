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

Requires **Python >=3.11**.

```bash
# From project root
pip install -e .                # core: fastapi, uvicorn, openai, psycopg2-binary, pgvector, numpy, pyyaml, etc.
pip install -e ".[dev]"         # dev: pytest, pytest-asyncio, aiofiles, cryptography, ruff, mypy, hypothesis
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
| `PG_DSN` | Stage 6, API server | PostgreSQL connection string (key-value or `postgresql://` URI format; key-value is auto-converted to URI for asyncpg) |
| `EMBEDDING_MODEL` | Stages 5–6, API server | Ollama model name |
| `EMBEDDING_BASE_URL` | Stages 5–6, API server | Ollama OpenAI-compatible endpoint |
| `EMBEDDING_API_KEY` | Stages 5–6, API server | Ollama auth (default: `ollama`) |
| `EMBEDDING_DIM` | Stages 5–6, API server | Embedding vector dimension |

### Step 6: Verify Setup

```bash
# Check Python
python3 --version               # should be 3.11+

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

### Stage 3: Analysis, Schema Alignment & State Relabeling

**Input:** `output_labeled.py`, `output_merged.py`, `data/data_labels/*.csv`

**Output:**

- `src/f003_reward_labeling/data/collector_analysis.json`
- `src/f003_reward_labeling/data/customer_analysis.json`
- `src/f001_schema_alignment/data/output_aligned.py`
- `src/f003_reward_labeling/data/output_rewarded.py`

Runs collector/customer turn analysis, schema alignment, state relabeling, then reward labeling. Schema alignment (`write_output_aligned`) automatically applies state relabeling after alignment using `relabel_state.py` and the maps in `data/data_labels/*.csv`. Reward labeling (`write_output_rewarded`) deduplicates records by `call_id` (keeping the first occurrence) before writing. Relabeling is applied **before** reward labeling so that `output_aligned.py` and `output_rewarded.py` both contain the final relabeled tags — no separate `output_relabeled.py` is needed.

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
- `POST /api/v1/session/start` — bind customer profile, map cust_tags to context bitmask (F014)
- `POST /api/v1/recommend` — real-time recommendation via shared `_run_turn()` (F014)
- `DELETE /api/v1/session/end` — close session (F014)
- `GET /health` / `GET /readyz` — health/readiness probes
- `POST /admin/reload-taxonomy` — hot-reload state keywords without restart
- Socket.IO events: `start_session`, `resume_session`, `customer_turn`, `collector_turn`, `end_session`

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
| **Canonical** | Already processed | `call_id`, `dialog`, `call_date`, `cust_no`, `coll_user_id`, `mob_typ`, `talk_time`, `plan_evaluation`, `customer_info` | Dict with 11 always-present Chinese keys (学历, 目前余额, etc.) + 7 optional |
| **Raw API** | From upstream system | `call_id`, `dialog`, `cust_no` | `custInfo` — JSON string of `[{tagName, ...}]` pairs |

Checks performed:
- All records have `call_id` (non-empty string) and `dialog` (string)
- Canonical records: all 9 top-level keys present, `customer_info` has expected Chinese keys, `mob_typ` in valid set
- Raw records: `custInfo` parses as JSON list of `{tagName, ...}` dicts
- Duplicate `call_id` detection

Use `--strict` to exit with code 1 on any error (for CI/pre-commit hooks).

---

## Tree Invariant Checking

Validate the built decision tree against 138 invariants across 10 categories (S, N, SE, D, G, C, SC, B, A, O):

```bash
python3 -m f004_decision_tree.check_tree          # F004 checks only
python3 -m f004_decision_tree.check_tree --scored  # F004 + F005 checks
```

Exit code 0 = all invariants pass. Exit code 1 = violations found (printed to stderr).

---

## Quick Start (Full Pipeline)

After completing **First-Time Setup** above:

```bash
# 0. Validate input data
python3 src/check_data_format.py data/data_input/matched_data.jsonl --strict

# 1. Run data pipeline (stages 1-3: clean → discover → align → relabel → reward)
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

Use `src/run_append.py` — the incremental append automation (F015). It appends new records at every stage without a full rebuild, leaving existing records intact. On success it appends to `matched_data.jsonl` and clears `new_data.jsonl`.

**Requires:** PostgreSQL + pgvector + Ollama bge-m3 running, `PG_DSN` set.

### Mode selection

`run_append.py` auto-detects the mode (override with `--mode`):

| Mode | Trigger | Input | What runs |
|------|---------|-------|-----------|
| `full` | `data/data_input/new_data.jsonl` non-empty | `new_data.jsonl` | pre-check → clean → merge → label → align → reward → tree → DB → append hook |
| `skip-cleaning` | `new_data.jsonl` empty | `src/f003_reward_labeling/data/new_rewarded.py` | tree build → score → DB upsert only (cleaning skipped) |

### Full run (new raw records)

1. **Place new records** in `data/data_input/new_data.jsonl` (one JSON record per line).
2. **Validate** (optional but recommended):

   ```bash
   python3 src/check_data_format.py data/data_input/new_data.jsonl --strict
   ```

3. **Run**:

   ```bash
   python3 src/run_append.py                    # auto-detects full (new_data.jsonl non-empty)
   ```

   On success: new records are appended to `matched_data.jsonl`, `new_data.jsonl` is cleared, tree + DB updated incrementally.

### Skip-cleaning run (already-rewarded records)

If the new records have already been cleaned/aligned/rewarded, place them in `src/f003_reward_labeling/data/new_rewarded.py` (a `.py` file with `results = [...]`, same schema as `output_rewarded.py`), then:

```bash
python3 src/run_append.py --mode skip-cleaning
```

Records whose `call_id` already exists in `output_rewarded.py` are skipped. The `matched_data.jsonl` append hook is skipped in this mode (a warning is printed — no raw input records to append).

### Options

```bash
python3 src/run_append.py --mode auto|full|skip-cleaning
python3 src/run_append.py --new-input data/data_input/new_data.jsonl
python3 src/run_append.py --rewarded-input src/f003_reward_labeling/data/new_rewarded.py
python3 src/run_append.py --dsn "dbname=icbc user=postgres"
```

### Errors

Any per-phase failure prints `WARNING: <phase> failed: <error>` to stderr and halts — existing data is left untouched (the append hook only runs after all phases succeed).

### Restart UIs

The API server loads the scored tree on startup, so restart it after any append:

```bash
python3 src/launch_ui.py
```

### Important notes

- **`new_data.jsonl` is cleared on success** — keep a copy elsewhere if you need an audit trail.
- **Database upserts are idempotent** for nodes and sentences (`ON CONFLICT ... DO UPDATE`). Taxonomy keywords use a MD5 natural-key unique index with `ON CONFLICT DO UPDATE SET frequency` (ADR-035).
- **Merge decisions are cached** — `src/f004_decision_tree/data/merge_decisions.json` is read and saved on each incremental tree build (ADR-036). Delete it to force re-merging.
- **Embeddings are computed only for new sentences** — the DB acts as an embedding cache; existing sentences are not re-embedded.
- **Orphan cleanup** — after upsert, sentences for new `call_id`s that exist in the DB but not the final tree are deleted (ADR-037, crash recovery).
- **Relabel maps are required** for the full path — `data/data_labels/*.csv` must exist.

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
| Orchestrator | — | `whole_pipeline.py`, `build_tree_and_db.py`, `run_append.py`, `add_records.py`, `launch_ui.py`, `run_api.py`, `check_data_format.py`, `check_new_records.py` | — |
| `f000_keyword_discovery/` | F000 | `discover_keywords.py`, `keyword_prompts.py`, `load_data.py` | `state_keywords.json`, `output_labeled.py` |
| `f001_schema_alignment/` | F001 | `align_schema.py`, `relabel_state.py` | `output_aligned.py` |
| `f003_reward_labeling/` | F003 | `analyze_collector_turns.py`, `analyze_customer_turns.py`, `define_willingness_levels.py`, `reward_label.py` | `output_rewarded.py` (deduplicated by `call_id`), `collector_analysis.json`, `customer_analysis.json` |
| `f004_decision_tree/` | F004 | `build_decision_tree.py`, `merge_collector.py`, `tree_transforms.py`, `check_tree.py`, `serve_tree.py` | `decision_tree.json`, `merge_decisions.json`, `dialog_records.json` |
| `f005_context_scoring/` | F005 | `score_tree.py`, `scoring_metrics.py`, `build_and_score_tree.py` | `decision_tree_scored.json` |
| `f006_retrieval_engine/` | F006 | `retrieval_engine.py`, `retrieval_ranking.py` | — (runtime: PostgreSQL) |
| `f007_infrastructure/` | F007 | `db.py`, `async_db.py`, `embeddings.py`, `llm_client.py`, `retry.py`, `config.py`, `logging.py`, `json_logging.py`, `backfill_embeddings.py`, `scheduler_state.py`, `migrations/runner.py` | — |
| `f008_state_extraction/` | F008 | `state_extraction.py` | — |
| `f009_api_server/` | F009 | `server.py`, `rate_limit.py`, `session_store.py`, `tag_mapping.py` | — |
| `f010_api_mock_ui/` | F010 | `debug.py`, `ui/` | — |

**Cross-module data flow:**

```
f000/output_labeled.py ──→ f001/align_schema.py ──→ f001/relabel_state.py ──→ f003/reward_label.py (dedup by call_id) ──→ f004/build_decision_tree.py
f004/decision_tree.json ──→ f005/score_tree.py ──→ f006/retrieval_engine.py
f005/decision_tree_scored.json ──→ f009/server.py ──→ f010/ui/
f000/state_keywords.json ──→ f009/server.py
```

---

## Tests

```bash
python3 -m pytest src/tests/            # all tests
python3 -m pytest src/tests/f005/       # specific module
```

Integration tests in `f005_context_scoring/` require `decision_tree_scored.json` to exist. Run `build_tree_and_db.py --skip-db` first if those tests fail.
