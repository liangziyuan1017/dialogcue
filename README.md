# Debt Collection Script Recommendation

> Recommend the single best collector reply in real time — grounded in which historical scripts actually led to repayment, not stylistic preference.

## Highlights

- **Historically grounded ranking** — top-1 collector scripts scored by repayment outcomes, profile fit, and semantic similarity
- **Two-phase system** — offline ingest (clean → label → decision tree → PostgreSQL) and online retrieve (`POST /recommend`)
- **Chinese debt-collection domain** — data-discovered state taxonomy (facts, emotions, willingness, collector actions), not a prescribed English ontology
- **Local embeddings, no per-call vector cost** — bge-m3 via Ollama (1024-dim) + PostgreSQL/pgvector hybrid search
- **Incremental ingest** — append new calls without full rebuild (`src/run_append.py`)
- **Built-in tooling** — Tree Explorer + Postman-style API mock / pipeline trace UI

## Problem

Debt-collection call centers need to recommend, **in real time**, the single best collector response given:

1. the customer's latest utterance, and
2. the conversation so far (state + recent context), and
3. the customer's profile (`custInfo` / context fields).

There is no off-the-shelf model for this:

| Gap | Why it matters |
|-----|----------------|
| Domain is Chinese-language and highly regulated | Generic chatbots ignore compliance tone and local phrasing |
| “Best” means **historically effective**, not fluent | Scripts that sound good may not correlate with repayment |
| Customer situations are sparse and combinatorial | Fixed taxonomies and rigid trees miss real patterns or over-fragment |
| Serving must stay fast and offline-capable | Bank / on-prem deployments often cannot depend on external embedding APIs |

Without a structured path from **historical calls → labeled states → scored scripts → retrieval**, agents fall back to memory, static playbooks, or unranked LLM drafts — none of which are auditable against repayment outcomes.

## Motivation

This repo exists to close that loop:

```text
historical dialogs  →  state taxonomy + rewards  →  decision tree + scores
                                                    →  PostgreSQL + vectors
                                                    →  top-1 script at call time
```

Concrete motivations from the feature specs:

- **Ground the ontology in data** ([F000](docs/features/F000-state-keyword-discovery.md), [ADR-001](docs/decisions/ADR-001-data-driven-keyword-discovery.md)) — Chinese collection conversations do not match English-prescribed emotion/fact lists.
- **Define success with a repayment reward** ([F003](docs/features/F003-reward-labeling.md)) — win rates need a binary ground truth per conversation, not human taste.
- **Structure history as a traversable tree** ([F004](docs/features/F004-decision-tree-construction.md), [ADR-011](docs/decisions/ADR-011-decision-tree-approach.md)) — retrieval needs shared decision points, not one chain per call.
- **Filter by profile and rank by quality** ([F005](docs/features/F005-context-tagging-quality-scoring.md)) — don't suggest mortgage scripts to customers without mortgages; prefer high historical win rate + semantic fit.
- **Serve externally over simple REST** ([F014](docs/features/F014-external-api-exposure.md)) — collection platforms typically cannot adopt Socket.IO; they need per-turn request/response.

Longer-term production goals (versioning, abstention, feedback loops) are sketched in [F018](docs/features/F018-production-recommendation-platform.md); the current repo ships the research→prototype platform through F017.

## Who this is for

| Audience | How they use this repo |
|----------|------------------------|
| **Collection-system integrators** | Call `POST /api/v1/session/start` → `POST /api/v1/recommend` → `DELETE /api/v1/session/end` (or Socket.IO / internal `POST /recommend`) from the live dialer |
| **Pipeline / data engineers** | Ingest `input_data.jsonl`, run `data_clean.py` + `build_tree_and_db.py`, append with `run_append.py`, tune `config.md` |
| **ML / dialogue researchers** | Inspect taxonomy, rewards, tree paths, ranking fusion, and ADRs; extend labeling or ranking without rewriting the API |
| **QA / compliance reviewers** | Use Tree Explorer and `/ui` pipeline traces to see *why* a script was chosen (node, scores, fallbacks) |
| **Operators / bank IT** | Prefer local Ollama embeddings + PostgreSQL; no external vector API required for serving |

If you only need a chatbot that “sounds helpful,” this project is the wrong tool. If you need **evidence-backed next-utterance recommendation** for Chinese collection dialogs, it is the right one.

## Overview

**Offline (Phase 1 — Ingest):** clean ASR dialogs → discover/label state taxonomy → score conversations for repayment reward → build and score the tree → load nodes, sentences, and embeddings into PostgreSQL.

**Online (Phase 2 — Retrieve):** extract customer state (LLM-first, keyword fallback) → accumulate conversation state → look up matching tree nodes → rank candidates with weighted fusion and return the top-1 script:

```text
0.35·win_rate + 0.25·vec_score + 0.10·sas + 0.10·bg_boost + 0.20·bitmask_score
```

(Weights are configurable in `config.md`.)

Stack: **Python ≥3.11**, **FastAPI + Socket.IO**, **PostgreSQL 16 + pgvector + pg_trgm**, **DeepSeek** (taxonomy / reward / online state extraction), **Ollama bge-m3** (embeddings).

End-to-end design, samples, latency budget, schema, and ADR index: [`SCBGE_GUIDELINE.md`](SCBGE_GUIDELINE.md). Feature roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Authors

Maintained in [`liangziyuan1017/debt_collection`](https://github.com/liangziyuan1017/debt_collection). Feature docs and ADRs under `docs/` are authoritative for detail; this README is the product-facing overview.

## Design considerations

These choices are deliberate; each links to the decision record or feature that owns it.

### 1. Data-driven taxonomy, not prescribed labels

Prescribed English taxonomies miss Chinese domain patterns (e.g. 多头欠款, 逃废债, 工资拖延). F000 discovers fact / emotion / willingness / collector-action groups from real turns, groups variants under canonical names, and allows suggested domain keywords with `source: "suggested"`.

See [ADR-001](docs/decisions/ADR-001-data-driven-keyword-discovery.md), [ADR-002](docs/decisions/ADR-002-keyword-grouping.md), [ADR-004](docs/decisions/ADR-004-collector-action-discovery.md), [ADR-005](docs/decisions/ADR-005-data-driven-willingness-levels.md).

### 2. Tree branches on customer situation; willingness labels sentences

Early trees used composite keys (facts + emotions + willingness + action) and collapsed into chains. The current model ([ADR-011](docs/decisions/ADR-011-decision-tree-approach.md)):

- **Nodes** = collector decision / action points
- **Branches** = customer facts or emotions (single-key steps)
- **Willingness** = metadata on each sentence in the pool, **not** a branch key

So under `financial_hardship`, both “weak” and “negotiating” scripts share a branch and compete at ranking time.

Opening/ending gestures are structural anchors (`initial_contact`, `normal_end`, `abrupt_end`); greetings pool at root while non-greeting opening actions still spawn `a:*` children for path tracing ([ADR-042](docs/decisions/ADR-042-opening-greetings-end-leaves.md)).

### 3. Soft profile matching + multi-signal ranking

Hard filters drop too many viable scripts on sparse data. F005/F006 use:

- **10-bit bitmask** from 18 `custInfo`-derived context fields for soft profile scoring (`matched_bits / required_bits`)
- **HWR** (Laplace-smoothed historical win rate from reward labels)
- **SAS** (intra-pool script analogy — diversity / redundancy)
- **`bg_boost`** (soft numeric/categorical profile proximity)
- **`vec_score`** (bge-m3 conversation-context similarity via pgvector)

Bitmask is a ranking signal, not a hard WHERE exclude ([ADR-020](docs/decisions/ADR-020-f005-bitmask-scoring-design.md)). Dense embeddings replaced char-ngram TF-IDF as the primary semantic signal so “没钱” ≈ “经济困难” ([ADR-024](docs/decisions/ADR-024-embedding-architecture.md)). Cosine is computed SQL-side (`<=>`) to avoid shipping raw vectors to Python ([ADR-028](docs/decisions/ADR-028-sql-side-cosine-scoring.md)).

### 4. One LLM call on the hot path (+ optional relabel)

Offline labeling is batch. Online, F008 extracts state LLM-first with keyword/tsvector fallback; a second offline LLM pass (old F002) was removed ([ADR-009](docs/decisions/ADR-009-eliminate-f002-llm-state-extraction.md)). Novel fact/emotion strings normalize through a shared relabel cascade (descriptions → CSV cache → LLM) so the taxonomy can grow without breaking node keys ([ADR-026](docs/decisions/ADR-026-open-set-extraction-relabel.md)).

### 5. Fallbacks over silence (with confidence cost)

Exact node miss → subset / key-drop; empty pool → descend into children; embed failure → win_rate + SAS only; exhausted → no recommendation. Confidence is reduced per fallback step so callers can abstain or escalate ([F006](docs/features/F006-retrieval-ranking-engine.md)).

### 6. Offline-first operations

Embeddings run locally (Ollama). Tree Explorer bundles JS libs for air-gapped use ([ADR-014](docs/decisions/ADR-014-bundled-js-libs.md)). Incremental append avoids full rebuild as the corpus grows ([F015](docs/features/F015-incremental-record-append.md), [ADR-035](docs/decisions/ADR-035-incremental-record-append-orchestrator.md)). F017 hardens large-corpus ingest (JSONL streaming, batched DB writes, DB-served indexes).

### Architecture sketch

```text
input_data.jsonl
    → data_clean.py          # clean / label / align / reward
    → build_tree_and_db.py   # decision tree + scores + PG load
    → PostgreSQL (nodes | sentences | taxonomy_keywords)

POST /recommend  (or /api/v1/*)
    → F008 state extract (+ relabel)
    → node lookup → bitmask + pgvector rank → top-1 script
```

| Layer | Choice | Why (short) |
|-------|--------|-------------|
| Database | PostgreSQL + pgvector | Metadata + vectors + FTS in one ACID store |
| Embeddings | bge-m3 via Ollama (1024-dim) | Semantic quality, local, no per-call cost |
| Online LLM | DeepSeek + keyword fallback | Semantic extraction with offline degrade path |
| API | FastAPI REST + Socket.IO + `/api/v1` | Integrators choose turn-managed or session-managed |
| Ranking | Unified weighted fusion | Tunable tradeoff among outcome, semantics, profile |
| Runtime DB | asyncpg (serve) / psycopg2 (build) | Async hot path; batch build keeps sync driver |

## Usage

### Who does what

| Goal | Start here |
|------|------------|
| Integrate a live collection system | [External session API](#external-session-api-f014) |
| Try a single recommendation locally | [Recommend a collector script](#recommend-a-collector-script) |
| Build / rebuild the knowledge base | [Offline pipeline](#offline-pipeline-one-liners) |
| Inspect why a path or script was chosen | Tree Explorer + `http://localhost:8000/ui` |
| Add new calls without full rebuild | `python3 src/run_append.py` with `data/data_input/new_data.jsonl` |

### Recommend a collector script

With the API running (see [Installation](#installation)):

```bash
curl -s http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_utterance": "我现在真的没钱还，能不能分期",
    "conversation_context": "催收员来电 告知逾期 客户表示经济困难",
    "conversation_state": {
      "branch_key": {"facts": []},
      "inherited_facts": [],
      "inherited_emotions": [],
      "willingness": null
    },
    "context": {
      "has_mortgage": true,
      "education": "bachelor",
      "days_delinquent": 30
    }
  }'
```

Typical response fields: `script_text`, `script_id`, `final_score`, `win_rate`, `vec_score`, `sas`, `bitmask_score`, updated `conversation_state`, `latency_ms`, `node_retrieved`.

Pass the returned `conversation_state` back on the next turn so facts/emotions accumulate along the tree path.

### External session API (F014)

For systems that manage calls externally:

```text
POST   /api/v1/session/start   # bind call_id + cust_tags → context
POST   /api/v1/recommend       # one customer turn → top-1 script
DELETE /api/v1/session/end     # close session
```

Shared core with Socket.IO (`start_session` / `customer_turn` / `end_session`) — no duplicated ranking logic. Details: [F014](docs/features/F014-external-api-exposure.md).

Interactive explorers:

| Surface | URL |
|---------|-----|
| Swagger | http://localhost:8000/docs |
| API mock + pipeline trace | http://localhost:8000/ui |
| Tree Explorer | http://localhost:8420/f004_decision_tree/ui/tree_explorer.html |

### Offline pipeline (one-liners)

```bash
# Validate input (exactly: call_id, dialog, custInfo)
python3 src/check_data_format.py data/data_input/input_data.jsonl --strict

# Clean → discover/label → align → reward
python3 src/data_clean.py data/data_input/input_data.jsonl

# Tree → score → PostgreSQL (+ embeddings)
python3 src/build_tree_and_db.py

# Append new records without full rebuild
python3 src/run_append.py

# Tree Explorer (:8420) + API (:8000)
set -a && source .env && set +a
PYTHONPATH=src python3 src/launch_ui.py
```

Input contract — one JSON object per line:

```json
{
  "call_id": "2346089320444241687",
  "dialog": "催收员：喂您好…；客户：唉；…",
  "custInfo": [{"tagName": "最高学历", "tagValue": "大专"}]
}
```

Incremental input uses the same schema in `data/data_input/new_data.jsonl`. On success, records are appended to `input_data.jsonl` and `new_data.jsonl` is cleared.

## Installation

**Requirements:** Python ≥3.11, PostgreSQL 16 with `vector` and `pg_trgm`, Ollama with `bge-m3`, DeepSeek API key.

```bash
git clone https://github.com/liangziyuan1017/debt_collection.git
cd debt_collection

# System deps (macOS examples)
brew install postgresql@16 pgvector ollama
brew services start postgresql@16
createdb icbc
psql icbc -c "CREATE EXTENSION IF NOT EXISTS vector"
psql icbc -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"
ollama pull bge-m3

# Python package
pip install -e .
# optional: pip install -e ".[dev]"

# Project root .env
cat > .env << 'EOF'
DEEPSEEK_API_KEY=sk-your-key-here
PG_DSN="dbname=icbc user=YOUR_OS_USERNAME"
EMBEDDING_MODEL=bge-m3
EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_DIM=1024
EOF
```

Quote key-value `PG_DSN` values that contain spaces. Tunables (ranking weights, ports, LLM retry) live in `config.md`.

Step-by-step setup, stage details, and troubleshooting: [`src/README.md`](src/README.md).

## Documentation

| Doc | What it covers |
|-----|----------------|
| [`SCBGE_GUIDELINE.md`](SCBGE_GUIDELINE.md) | End-to-end system guideline (phases, samples, ADRs, latency, schema) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Feature status + consolidated architecture decisions |
| [`src/README.md`](src/README.md) | Setup, pipeline stages, launch commands |
| [`data/README.md`](data/README.md) | Input/output JSONL layout and taxonomies |
| [`docs/features/`](docs/features/) | Per-feature specs (F000–F018) — problem statements and acceptance criteria |
| [`docs/decisions/`](docs/decisions/) | Architecture Decision Records — design tradeoffs |

## Feedback and Contributing

Issues and feature requests are welcome on the [GitHub repo](https://github.com/liangziyuan1017/debt_collection). Before changing ranking, taxonomy, or ingest contracts, read the relevant feature **Why** section and ADR — starting from [`docs/ROADMAP.md`](docs/ROADMAP.md) or the ADR index in [`SCBGE_GUIDELINE.md`](SCBGE_GUIDELINE.md#adr-index).
