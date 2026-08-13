---
id: F009
name: REST API + Socket.IO Server
status: review
depends_on: [F007, F007b, F008]
created: 2026-06-24
updated: 2026-06-26
review_submitted: 2026-06-25
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F009: REST API + Socket.IO Server

Real-time recommendation API for the debt collection script system. Two interfaces: REST for single-turn queries, Socket.IO for live call sessions with streaming state accumulation.

## Goal

Create FastAPI server with `POST /recommend` endpoint and Socket.IO session management. Covers **Steps 8-9** of the implementation steps (see [F007-F009-implementation-steps.md](F007-F009-implementation-steps.md)).

## Passing Criteria

- `POST /recommend` returns 200 with valid output schema
- Missing required fields → 400
- `conversation_state` accumulation across multiple calls
- Socket.IO `start_session` → `customer_turn` → `end_session` flow
- State accumulation is automatic in Socket.IO sessions
- `collector_turn` extracts actions

## Files

- NEW: `src/f009_api_server/__init__.py`
- NEW: `src/f009_api_server/server.py`
- NEW: `src/tests/f009_api_server/test_recommend.py`
- NEW: `src/tests/f009_api_server/test_socket.py`

---

## REST API

### `POST /recommend`

Single-turn recommendation. Caller manages `conversation_state` accumulation manually.

**Request:**

```json
{
  "customer_utterance": "我现在真的没钱还，能不能分期",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还",
  "conversation_state": {
    "facts": ["financial_hardship"],
    "emotions": []
  },
  "context": {
    "has_auto_loan": false,
    "has_mortgage": true,
    "credit_rating": "good",
    "days_delinquent": 30,
    "total_debt": 62209,
    "external_debt": 436762,
    "has_negotiation_history": false,
    "available_plans": ["reduction"],
    "social_insurance_stable": false,
    "card_restricted": false,
    "is_cash_out_customer": false,
    "external_debt_institutions": 9,
    "interest_ratio": 0.04,
    "installment_ratio": 0.0,
    "age": 49,
    "gender": "女",
    "education": "unknown",
    "industry": "专业性事务所"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `customer_utterance` | string | yes | Customer's most recent turn |
| `conversation_context` | string | no | Past ~100 words of dialog for vector matching |
| `conversation_state` | object | yes | Accumulated state from prior turns (pass back from previous response) |
| `conversation_state.facts` | string[] | yes | e.g. `["financial_hardship", "request_installment"]` |
| `conversation_state.emotions` | string[] | yes | e.g. `["pleading", "disappointment"]` |
| `conversation_state.actions` | string[] | yes | e.g. `["empathy", "plan_proposal"]` |
| `conversation_state.willingness` | string or null | yes | e.g. `"conditional"`, `"negotiating"`, `"strong"`, or `null` |
| `context` | object | yes | Customer profile (same schema as `output_aligned.jsonl` `context` field) |

**Response (200):**

```json
{
  "script_text": "我理解您目前的困难，我们可以帮您申请分期...",
  "script_id": "2320459500460373224_t38",
  "state_id": "financial_hardship|pleading|request_installment",
  "win_rate": 0.67,
  "vec_score": 0.89,
  "sas": 0.72,
  "final_score": 0.685,
  "confidence": 0.9,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["pleading"],
    "actions": []
  },
  "ranking_weights": {
    "win_rate": 0.40,
    "vec_score": 0.30,
    "sas": 0.15,
    "bg_boost": 0.15
  },
  "fallbacks": [],
  "latency_ms": 1050
}
```

| Field | Type | Description |
|---|---|---|
| `script_text` | string | Recommended collector response text |
| `script_id` | string | Source turn identifier (format: `{call_id}_t{turn_index}`) |
| `state_id` | string | Path signature of the matched node |
| `win_rate` | float | Historical effectiveness (HWR) |
| `vec_score` | float | Vector cosine similarity to `conversation_context` |
| `sas` | float | Script Analogy Score (TF-IDF diversity within pool) |
| `final_score` | float | Weighted fusion of all signals |
| `confidence` | float | Overall confidence (degraded by fallbacks) |
| `extraction_method` | string | `"llm"` or `"keyword"` |
| `conversation_state` | object | Updated state — **pass back on next turn** |
| `ranking_weights` | object | Weight configuration used |
| `fallbacks` | string[] | Which fallbacks fired (e.g. `["key_drop", "bitmask_relax"]`) |
| `latency_ms` | int | Total processing time |

**Error responses:**

| Status | Condition |
|---|---|
| 400 | Missing required fields |
| 404 | No recommendation found after all fallbacks |
| 503 | LLM unavailable and keyword fallback also failed |

---

## Processing Pipeline

Each `POST /recommend` call executes these steps in sequence (see SCBGE_GUIDELINE.md Phase 2 for full detail):

### Step 1: State Extraction (LLM-first)

DeepSeek LLM extracts `{facts, emotions, actions, confidence}` from `customer_utterance` given the taxonomy from `state_keywords.json`. Fallback: PostgreSQL tsvector keyword search if LLM fails.

**Latency**: ~800-1200ms (LLM) | ~5ms (keyword fallback)

### Step 2: State Accumulation

Merge new extractions into `conversation_state`. Deduplicate, preserve insertion order.

**Latency**: <1ms

### Step 3: Path Signature

`signature = "|".join(sorted(facts + emotions + actions))`

**Latency**: <1ms

### Step 4: Node Lookup (DB-backed)

Normalize the accumulated facts, emotions, and actions into a label set and query the indexed `nodes.labels` JSONB column. The query is bounded to the most specific candidates. Fallback: progressive tag removal (strip lowest-frequency tag, retry, -0.1 confidence per removal).

**Latency**: <1ms

### Step 5: Candidate Retrieval + Bitmask Filter (PostgreSQL)

```sql
SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
       bg_background, conversation_context, embedding
FROM sentences
WHERE node_id = $node_id
  AND (bg_bitmask_int & $query_bitmask) = bg_bitmask_int;
```

Fallback: bitmask relaxation (drop lowest bit, -0.05 confidence per relaxation).

**Latency**: ~2-5ms

### Step 6: Vector Semantic Match (pgvector)

Embed `conversation_context` via bge-m3 embedding model (Ollama) → 1024-dim vector → cosine similarity against candidate `embedding` columns. The live `conversation_context` is first truncated to its **last 100 words** via `_last_n_words()` (server.py, `_EMBED_CONTEXT_MAX_WORDS = 100`) before embedding, bounding `query_vec` to a recent context window regardless of how much history the caller sends. Applied at both embedding call sites (`/recommend` and `_run_turn`).

**Latency**: ~50-100ms (bge-m3 embed via Ollama) + ~2ms (pgvector)

### Step 7: Rerank (Weighted Fusion)

```
final_score = 0.35 × win_rate + 0.25 × vec_score + 0.10 × sas + 0.10 × bg_boost + 0.20 × bitmask_score
```

**Latency**: <1ms

### Hybrid Search SQL (Steps 5+6+7 combined)

When `bg_boost` is negligible, a single SQL query handles retrieval + filter + vector + rank:

```sql
WITH candidates AS (
  SELECT script_id, script_text, win_rate, sas, bg_bitmask_int, bg_background,
         1 - (embedding <=> $query_vec) AS vec_score
  FROM sentences
  WHERE node_id = $node_id
    AND (bg_bitmask_int & $query_bitmask) = bg_bitmask_int
)
SELECT script_id, script_text, win_rate, sas, vec_score, bg_background,
       (0.40 * win_rate + 0.30 * vec_score + 0.15 * sas) AS final_score
FROM candidates
ORDER BY final_score DESC
LIMIT 1;
```

When `bg_boost` is needed, fetch candidates first then compute `bg_boost` + `final_score` in Python.

---

## Socket.IO Interface

For live call sessions where the server manages `conversation_state` accumulation automatically. Client sends utterances as they happen; server streams back recommendations.

### Connection

```
ws://localhost:8000/socket.io
```

### Events

#### `start_session`

Initialize a call session with customer profile. Server creates a session and returns the session ID.

**Emit:**

```json
{
  "cust_no": "0100252354",
  "context": {
    "has_auto_loan": false,
    "has_mortgage": true,
    "credit_rating": "good",
    "days_delinquent": 30,
    "total_debt": 62209,
    "external_debt": 436762,
    "has_negotiation_history": false,
    "available_plans": ["reduction"],
    "social_insurance_stable": false,
    "card_restricted": false,
    "is_cash_out_customer": false,
    "external_debt_institutions": 9,
    "interest_ratio": 0.04,
    "installment_ratio": 0.0,
    "age": 49,
    "gender": "女",
    "education": "unknown",
    "industry": "专业性事务所"
  }
}
```

**Ack:**

```json
{
  "session_id": "sess_abc123",
  "conversation_state": {
    "facts": [],
    "emotions": [],
    "actions": []
  }
}
```

---

#### `customer_turn`

Send a customer utterance during an active session. Server runs the full pipeline (Steps 1-7), accumulates `conversation_state` automatically, and returns recommendation.

**Emit:**

```json
{
  "session_id": "sess_abc123",
  "utterance": "我现在真的没钱还，能不能分期",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还"
}
```

**Ack:**

```json
{
  "script_text": "我理解您目前的困难，我们可以帮您申请分期...",
  "script_id": "2320459500460373224_t38",
  "state_id": "financial_hardship|pleading|request_installment",
  "win_rate": 0.67,
  "vec_score": 0.89,
  "sas": 0.72,
  "final_score": 0.685,
  "confidence": 0.9,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["pleading"],
    "actions": []
  },
  "ranking_weights": {"win_rate": 0.35, "vec_score": 0.25, "sas": 0.10, "bg_boost": 0.10, "bitmask_score": 0.20},
  "fallbacks": [],
  "latency_ms": 1050
}
```

Server automatically accumulates `conversation_state` across turns within the session. No need for client to pass it back.

---

#### `collector_turn`

Record the collector's actual response. Server also extracts collector actions (e.g. `empathy`, `plan_proposal`, `pressure`) via LLM and accumulates them into `conversation_state.actions`. Does not trigger a script recommendation.

**Emit:**

```json
{
  "session_id": "sess_abc123",
  "utterance": "我理解您的困难，那您看能不能先还一部分呢？"
}
```

**Ack:**

```json
{
  "recorded": true,
  "extracted_actions": ["empathy"],
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["pleading"],
    "actions": ["empathy"]
  }
}
```

---

#### `end_session`

Close a call session. Server returns the full session transcript for logging.

**Emit:**

```json
{
  "session_id": "sess_abc123"
}
```

**Ack:**

```json
{
  "session_id": "sess_abc123",
  "duration_seconds": 180,
  "turn_count": 5,
  "final_conversation_state": {
    "facts": ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"],
    "emotions": ["disappointment", "cooperative"],
    "actions": ["plan_proposal", "closure"]
  },
  "transcript": [
    {"turn": 1, "role": "customer", "utterance": "喂", "recommendation": {}},
    {"turn": 2, "role": "collector", "utterance": "嗯嗯，嗯对。", "extracted_actions": ["greeting"]},
    {"turn": 3, "role": "customer", "utterance": "最近经济压力有点大...", "recommendation": {}}
  ]
}
```

---

#### `recommendation` (server push)

Emitted by server when a recommendation is ready. Useful if state extraction is slow — client can show a loading state and update when this event arrives.

**Listen:**

```json
{
  "session_id": "sess_abc123",
  "script_text": "我理解您目前的困难，我们可以帮您申请分期...",
  "script_id": "2320459500460373224_t38",
  "state_id": "financial_hardship|pleading|request_installment",
  "win_rate": 0.67,
  "vec_score": 0.89,
  "sas": 0.72,
  "final_score": 0.685,
  "confidence": 0.9,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["pleading"],
    "actions": []
  },
  "ranking_weights": {"win_rate": 0.35, "vec_score": 0.25, "sas": 0.10, "bg_boost": 0.10, "bitmask_score": 0.20},
  "fallbacks": [],
  "latency_ms": 1050
}
```

---

## Socket.IO Session Walkthrough

Live call using call `2317941550352385028` (customer 0100252354, 专业性事务所, age 49). Server manages all state.

```
Client                          Server
  │                               │
  │── start_session ─────────────►│  session_id: sess_abc123
  │                               │  conversation_state: {facts:[], emotions:[], actions:[]}
  │◄──────────────────────────────│
  │                               │
  │── customer_turn("喂") ───────►│  Step 1: LLM → {} (nothing extracted)
  │                               │  Step 2: state = {facts:[], emotions:[], actions:[]}
  │                               │  Step 3: signature = ""
  │                               │  Step 4: node_id = 1 (initial_contact)
  │                               │  Step 5-7: PG query + vector + rerank
  │◄── "嗯嗯，嗯对。" ───────────│  state_id: initial_contact, win_rate: 0.333
  │                               │
  │── collector_turn("嗯嗯，嗯对")►│  LLM extracts action: "greeting"
  │◄── actions: ["greeting"] ─────│  conversation_state.actions = ["greeting"]
  │                               │
  │── customer_turn("最近经济压力有点大")►│  Step 1: LLM → {facts:["financial_hardship"]}
  │                               │  Step 2: state = {facts:["financial_hardship"], actions:["greeting"]}
  │                               │  Step 3: signature = "financial_hardship|greeting"
  │                               │  Step 4: node_id → f:financial_hardship
  │                               │  Step 5-7: PG query + vector + rerank
  │◄── "我理解您的困难..." ──────│  state_id: financial_hardship, win_rate: 0.60
  │                               │
  │── customer_turn("整个账单分期...")►│  Step 1: LLM → {facts:["request_installment"], emotions:["disappointment"]}
  │                               │  Step 2: state = {facts:["financial_hardship","request_installment"],
  │                               │                    emotions:["disappointment"], actions:["greeting"]}
  │                               │  Step 3: signature = "financial_hardship|disappointment|greeting|request_installment"
  │                               │  Step 4: node_id → deep node
  │◄── "建议你去还最低还款..." ──│  state_id: financial_hardship|disappointment|...|request_installment
  │                               │
  │── end_session ───────────────►│  Returns full transcript
  │◄── {duration: 180s, turns: 5}│
```

---

## Data Schemas

### `conversation_state`

Accumulated across turns. Taxonomy group names from `state_keywords.json`.

| Category | Values | Source |
|---|---|---|
| `facts` | `financial_hardship`, `request_installment`, `multiple_debts`, `salary_delay`, `income_statement`, `ability_to_pay`, `account_frozen`, `prior_contact_attempt`, `previous_agreement`, `high_interest`, `bankruptcy`, `illness`, `family_illness`, ... | LLM extraction from customer utterance |
| `emotions` | `pleading`, `resistant`, `anxious`, `angry`, `cooperative`, `disappointment`, `distress`, `frustration`, ... | LLM extraction from customer utterance |
| `actions` | `empathy`, `pressure`, `information`, `plan_proposal`, `greeting`, `closure`, ... | LLM extraction from collector utterance |

### `context`

Customer profile. Same schema as `output_aligned.jsonl` `context` field, derived from `custInfo` Chinese fields.

| Field | Type | Source `customer_info` key | Transform |
|---|---|---|---|
| `has_auto_loan` | bool | `他行是否有车贷` / `我行是否有车贷` | contains "有车贷" |
| `has_mortgage` | bool | `他行是否有房贷` / `我行是否有房贷` | contains "有房贷" |
| `credit_rating` | string | `24期缴款评等` | first char: Z→good, B→moderate, 0→bad |
| `days_delinquent` | int | `mob_typ` | M1→30 |
| `total_debt` | int | `总欠款` | parse numeric |
| `external_debt` | int | `外部欠款金额` | parse numeric |
| `has_negotiation_history` | bool | `历史协商情况` | ≠ "无协商历史" |
| `available_plans` | string[] | `当前可使用的协商方案` | parse plan types |
| `social_insurance_stable` | bool | `社保缴纳情况` | has "有社保" and not "灵活就业" |
| `card_restricted` | bool | `是否管制` | = "已管制" |
| `is_cash_out_customer` | bool | `是否为套现客户` | = "套现客户" |
| `external_debt_institutions` | int | `外部共债机构数` | parse count |
| `interest_ratio` | float | `利息占欠款比例` | parse percentage |
| `installment_ratio` | float | `分期金额占欠款比例` | parse percentage |
| `age` | int | `年龄` | parse int |
| `gender` | string | `性别` | direct |
| `education` | string | `学历` | map: 未填→unknown, ... |
| `industry` | string | `行业` | direct |

### Bitmask encoding

10-bit integer derived from `context` for O(1) filtering. Same as `scoring_metrics.py BITMASK_FIELDS`:

| Bit | Field |
|---|---|
| 0 | `has_auto_loan` |
| 1 | `has_mortgage` |
| 2 | `has_negotiation_history` |
| 3 | `social_insurance_stable` |
| 4 | `credit_rating_good` |
| 5 | `card_restricted` |
| 6 | `is_cash_out_customer` |
| 7 | `has_complaint_history` |
| 8 | `has_legal_tools` |
| 9 | `is_negotiation_brain_customer` |

---

## Ranking

Weighted fusion of five signals:

```
final_score = 0.35 × win_rate + 0.25 × vec_score + 0.10 × sas + 0.10 × bg_boost + 0.20 × bitmask_score
```

| Signal | Weight | Source | Range |
|---|---|---|---|
| `win_rate` | 0.35 | HWR from `reward` labels in `output_rewarded.jsonl` | [0, 1] |
| `vec_score` | 0.25 | pgvector cosine similarity on `conversation_context` embeddings | [0, 1] |
| `sas` | 0.10 | Char bigram TF-IDF cosine within sentence pool | [0, 1] |
| `bg_boost` | 0.10 | Profile match heuristic (education, risk level, complaint, delinquency) | [0, 0.12] |
| `bitmask_score` | 0.20 | Context bitmask match (customer profile → sentence constraints) | [0, 1] |

---

## Fallback Hierarchy

| Condition | Fallback | Confidence Impact |
|---|---|---|
| Exact path signature miss | Strip lowest-frequency tag, retry | -0.1 per removal |
| All tags stripped, still miss | Use root node (`initial_contact`) | -0.2 |
| Bitmask filter returns empty | Relax bitmask (drop lowest bit) | -0.05 per relaxation |
| LLM state extraction fails | PostgreSQL tsvector keyword search | -0.1 |
| LLM embedding fails | Rank by `win_rate` + `sas` only (no `vec_score`) | -0.1 |
| All fallbacks exhausted | Return 404 | 0.0 |

---

## Latency Budget

| Step | Latency | Notes |
|---|---|---|
| State extraction (LLM) | 800-1200ms | Dominated by DeepSeek API call |
| State accumulation | <1ms | In-memory set operations |
| Path signature | <1ms | String join |
| Node lookup | <1ms | Hash map O(1) |
| Candidate retrieval + bitmask | 2-5ms | Indexed PG query |
| Vector embedding (query) | 50-100ms | bge-m3 embed via Ollama |
| Vector similarity | 1-2ms | pgvector HNSW or brute-force cosine |
| Rerank | <1ms | Arithmetic on <20 candidates |
| **Total** | **~900-1300ms** | Dominated by LLM; without LLM: <10ms |

---

## Startup

```bash
# REST API only
uvicorn src.f009_api_server.server:app --host 0.0.0.0 --port 8000

# REST + Socket.IO
uvicorn src.f009_api_server.server:app --host 0.0.0.0 --port 8000 --ws websocket
```

On startup, the server:
1. Connects to PostgreSQL (pgvector) for indexed node-label lookup, sentence retrieval, provenance, and vector search; it does not load the scored tree or indexes into `app.state`
2. Loads `state_keywords.json` → taxonomy for state extraction
3. Initializes the bge-m3 embedding client via Ollama at `EMBEDDING_BASE_URL` (default `http://localhost:11434/v1`)
4. Initializes the DeepSeek LLM client from `DEEPSEEK_API_KEY` in `.env` (for state extraction)

## Links

- ~~full_processing.md~~ — Phase 2 pipeline detail (no longer in repo; see `SCBGE_GUIDELINE.md` Phase 2)
- [F007-F009-implementation-steps.md](F007-F009-implementation-steps.md) — Steps 8-9 implementation
- [implementation-plan.md](F009-implementation-plan.md)

## Implementation Plan

See [implementation-plan.md](F009-implementation-plan.md)
