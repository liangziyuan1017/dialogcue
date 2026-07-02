# SCBGE Guideline: Debt Collection Script Recommendation System

> This document is the comprehensive project guideline. It documents every processing phase end-to-end: what each phase does, why it was designed that way, all data inputs and outputs (with samples), the design considerations and decisions behind each step, the latency budget, fallback hierarchy, scaling path, and a full ADR index. 

> Feature docs and ADRs remain the authoritative source for detail; this guideline synthesizes them into one navigable whole.

---

## System Vision

### Problem

Debt-collection call centers need to recommend, in real time, the single best collector response given the customer's current utterance and the conversation so far. There is no off-the-shelf model: the domain is Chinese-language, highly regulated, and the "best" response is historically grounded (which collector scripts actually led to repayment), not stylistically preferred.

### Approach

Build a two-phase system:

1. **Offline (Phase 1 — Ingest):** Mine 31 historical call recordings to discover a state taxonomy (facts, emotions, willingness, collector actions), label every turn, score each conversation for repayment reward, construct a collector decision tree keyed by customer state, tag each tree sentence with a customer-profile bitmask + quality scores + semantic embedding, and load everything into PostgreSQL + pgvector.

2. **Online (Phase 2 — Retrieve):** For each `POST /recommend` call, extract the customer's state from their utterance (LLM-first, keyword fallback), accumulate it into the conversation state, compute a permutation-insensitive node key, look up matching tree nodes O(1), aggregate their sentence pools, and rank the survivors by unified weighted fusion (`0.40·win_rate + 0.30·vec_score + 0.15·sas + 0.15·bg_boost * soft_bit_mask`) -- configurable via configs. Return the top-1 collector script.

### Architecture

- **Database**: PostgreSQL + pgvector + pg_trgm — single database for metadata, 1024-dim vectors, 10-bit bitmask soft scoring, and full-text search.
- **Embeddings**: bge-m3 (1024-dim) served locally via Ollama, OpenAI-compatible API. No external per-call cost; offline-capable (ADR-024).
- **LLM**: DeepSeek for offline taxonomy discovery / reward labeling / turn labelling, and for the single online state-extraction call in the hot path.
- **API**: FastAPI, `POST /recommend` (REST, caller manages conversation state) + Socket.IO session interface (server manages state accumulation automatically). See F009.
- **UI tooling**: F010 — Postman-style mock panel + pipeline trace + sentence pool inspector, served at `/ui`. See [Tooling](#tooling-f010-ui--debug-endpoint).

### Feature Map

| ID | Name | Phase | Status | Doc |
|----|------|-------|--------|-----|
| F000 | State Keyword Discovery | 1 (1.2) | complete | [F000](docs/features/F000-state-keyword-discovery.md) |
| F001 | Data Schema Alignment | 1 (1.3) | complete | [F001](docs/features/F001-data-schema-alignment.md) |
| F002 | ~~LLM State Extraction~~ | — | removed (ADR-009) | — |
| F003 | Reward Labeling | 1 (1.4) | complete | [F003](docs/features/F003-reward-labeling.md) |
| F004 | Decision Tree Construction | 1 (1.5) | complete | [F004](docs/features/F004-decision-tree-construction.md) |
| F005 | Context Tagging & Quality Scoring | 1 (1.6) | complete | [F005](docs/features/F005-context-tagging-quality-scoring.md) |
| F006 | Retrieval & Ranking Engine | 2 (2.2–2.7) | complete | [F006](docs/features/F006-retrieval-ranking-engine.md) |
| F007 | Infrastructure Layer | 2 | review | [F007](docs/features/F007-infra-layer.md) |
| F007b | Vector Retrieval Integration | 2 | review | [F007b](docs/features/F007b-vector-retrieval-integration.md) |
| F008 | Online State Extraction Module | 2 (2.1) | review | [F008](docs/features/F008-state-extraction.md) |
| F009 | REST API + Socket.IO Server | 2 | review | [F009](docs/features/F009-api-server.md) |
| F010 | API Mock + System Status UI | tooling | complete | [F010](docs/features/F010-api-mock-system-status-ui.md) |

### Dependency Graph

```
F000 ──► F001 ──► F003 ──► F004 ──► F005 ──► F006
                                     │           │
                                     └────► F007 ◄┘
                                              │
                                              ▼
                                            F007b
                                              │
                                              ▼
                                            F008
                                              │
                                              ▼
                                            F009
```

### Data Flow

```
data/matched_data.jsonl  (31 call records, raw)
        │
        ▼  F000  (LLM taxonomy discovery + turn labelling)
state_keywords.json          output_labeled.py   (per-turn state labels)
        │                            │
        ▼  F001  (schema alignment, carry F000 labels, derive context) ──────────────┐
output_aligned.py  (turns_annotated + context + reward:null)                          │
        │                                                                            │
        ▼  F003  (LLM reward R∈{0,1} + counterfactual credit)                         │
output_rewarded.py  (reward + reward_action_credit + reward_evidence)                 │
        │                                                                            │
        ▼  F004  (segment extraction → fact-by-fact walk → transforms → dedup)        │
decision_tree.json  (309 nodes, 782 sentences, DAG)                                   │
        │                                                                            │
        ▼  F005  (bitmask tagging + HWR + SAS + conversation_context)                 │
        ▼  F007b (bge-m3 embedding of conversation_context)                           │
decision_tree_scored.json  (backward-compat JSON)                                     │
        │                                                                            │
        ▼  F007  (load into PostgreSQL)                                               │
PostgreSQL: nodes │ sentences (embedding vector(1024), tsvector) │ taxonomy_keywords  │
        │                                                                            │
        ▼  F008 + F006 + F009  (online retrieval)                                    │
POST /recommend  →  state extraction  →  relabel  →  node lookup  →  bitmask score  →  vector rank  →  top-1 script
                                          ↑__________________|
                                            *_relabeled grows (ADR-026)
```

### Architecture Decisions Summary

| Decision | Choice | ADR |
|---|---|---|
| Database | PostgreSQL + pgvector | — |
| Embeddings | bge-m3 via Ollama (1024-dim, OpenAI-compatible) | ADR-024 |
| Conversation context similarity | Vector cosine via pgvector | ADR-024 |
| SAS (Script Analogy Score) | Char bigram TF-IDF cosine within pool | ADR-020 |
| Full-text search | PostgreSQL tsvector + GIN | — |
| Ranking | Unified weighted fusion | ADR-024 |
| State extraction | LLM-first (DeepSeek), keyword fallback | ADR-009 |
| Taxonomy | Data-discovered, not prescribed | ADR-001..005 |
| Context constraints | 21-field mapping → 10-bit bitmask | ADR-006, ADR-020 |
| API | FastAPI + Socket.IO | — |

---

## Phase 1: Ingest (offline, batch)

All data preparation happens offline. The output is a PostgreSQL database loaded
with the decision tree, scored sentences, and pre-computed embeddings.

### Step 1.1: Raw Data

#### What this does

Ingests the raw source corpus: 31 debt-collection call records in JSONL, each
containing the raw dialog string, call metadata, and a `customer_info` block of
~27 Chinese-string profile fields. No transformation happens here — this is the
input contract for the entire pipeline.

#### Design considerations & decisions

- The corpus is small (31 records, 805 turns) — prototype scope. Taxonomy
  discovery and frequency stats are accepted as unstable at this scale; the
  system is designed to broaden with data (ADR-003 suggests domain keywords).
- Raw `customer_info` fields are Chinese strings, unusable for O(1) filtering.
  F001 (ADR-006) maps them to 21 typed English fields later.

**Source**: `/data/matched_data.jsonl` — 31 call records in JSONL format.

Each record has these exact fields:

```json
{
  "call_id": "2317941550352385028",
  "dialog": "催收员：唉，您好...；客户：喂；...",   // raw dialog string, turns separated by ；
  "call_date": "20260506",
  "cust_no": "0100252354",
  "coll_user_id": "SX17625",
  "mob_typ": "M1",
  "talk_time": "613",
  "plan_evaluation": "| 类型 | 执行情况 | 关键证据 | ...",
  "customer_info": {
    "统计日期": "2026-05-13",
    "客户号": "0000000100252354",
    "年龄": "49",
    "性别": "女",
    "申请卡片时间": "2003-10-01",
    "学历": "未填",
    "行业": "专业性事务所",
    "社保缴纳情况": "有社保，但为灵活就业参保，稳定性不高",
    "他行是否有房贷": "他行有房贷，欠款121991",
    "他行是否有车贷": "他行无车贷",
    "我行是否有房贷": "我行无房贷",
    "我行是否有车贷": "我行无车贷",
    "是否为套现客户": "非套现客户",
    "持卡客户是否疑似代理中介投诉": "否",
    "总欠款": "62209",
    "利息占欠款比例": "4%",
    "分期金额占欠款比例": "0%",
    "是否管制": "可正常使用卡片",
    "24期缴款评等": "ZZZZZZZZZZZZZZBBB0",
    "外部欠款金额": "外部欠款总余额436762...",
    "外部共债机构数": "外部共债机构数共9家，其中逾期的机构共1家",
    "历史协商情况": "无协商历史",
    "历史投诉情况": "客户历史没有重渠投诉",
    "当前可使用的协商方案": "001账号欠款61967元，有协商方案，要么办理调减方案;...",
    "当前可使用的法务工具": "无可用的法务工具",
    "近一个月callid": "Y2317585420622995027,...",
    "是否完成总结": "0",
    "是否谈判大脑客户": "N"
  }
}
```

### Step 1.2: F000 — State Keyword Discovery + Turn Labelling

#### What this does

Discovers the state taxonomy (facts, emotions, willingness levels, collector
actions) from real conversation data via DeepSeek LLM, rather than prescribing
it. Then labels each turn with the discovered state keywords. Outputs the
taxonomy JSON plus a per-turn labelled Python file. 493 of 805 turns are
labelled; filler turns ("嗯", "对", "好") are left unlabeled.

#### Design considerations & decisions

- **KD-1 / ADR-001**: Discover keywords from data, not prescribe — Chinese
  debt-collection patterns differ from English assumptions.
- **KD-2 / ADR-002**: Group same-meaning keyword variants under canonical names
  (e.g. "没钱" ≈ "经济困难") to prevent sentence-pool fragmentation.
- **KD-3 / ADR-003**: Include suggested domain keywords (`source: "suggested"`,
  freq 0) for rare-but-critical states not in 31 records. (since the suggested ones are not rare cases, there are similar ones in the observed data, these are removed)
- **KD-4 / ADR-004**: Discover collector action types from data too — fixed
  7-type enum didn't match observed Chinese collector behavior.
- **KD-5 / ADR-005**: Willingness level count is data-driven (natural
  clustering yielded 5 levels: resistant→weak→conditional→negotiating→strong).
- **Risk**: LLM may invent ungrounded keywords → mitigated by requiring verbatim
  `example_turn` for every observed keyword; suggested keywords explicitly
  flagged.

**Input**: All turns across 31 records from `/data/matched_data.jsonl`

**Process**:
1. **Keyword discovery**: LLM groups same-meaning keywords into canonical groups (ADR-001: data-driven, not prescribed; ADR-002: group variants under canonical names)
2. **Turn labelling**: LLM labels each turn with state keywords from the discovered taxonomy — facts, emotions, willingness (customer) or action (collector). Turns with no meaningful state are left unlabeled.

**Output 1**: `/src/f000_keyword_discovery/state_keywords.json` (taxonomy)

```json
{
  "facts": [
    {
      "group_name": "financial_hardship",
      "keywords": ["最近经济压力有点大", "经济困难", "现在没有钱", "没有钱", ...],
      "frequency": 29,
      "example_turn": "...",
      "source": "observed"
    },
    {
      "group_name": "request_installment",
      "keywords": ["整个账单分期", "分期完之后信用卡取消", ...],
      "frequency": 6,
      "source": "observed"
    },
    {"group_name": "multiple_debts", "keywords": [...], "frequency": 5, ...},
    {"group_name": "salary_delay", "keywords": [...], "frequency": 5, ...},
    {"group_name": "income_statement", "keywords": [...], "frequency": 4, ...},
    {"group_name": "ability_to_pay", "keywords": [...], "frequency": 4, ...},
    ...
  ],
  "emotions": [
    {"group_name": "pleading", "keywords": [...], "frequency": 12, ...},
    {"group_name": "resistant", "keywords": [...], "frequency": 8, ...},
    {"group_name": "disappointment", "keywords": [...], "frequency": 6, ...},
    ...
  ],
  "collector_actions": [
    {"group_name": "empathy", "keywords": [...], "frequency": 15, ...},
    {"group_name": "pressure", "keywords": [...], "frequency": 10, ...},
    {"group_name": "information", "keywords": [...], "frequency": 20, ...},
    ...
  ],
  "willingness_levels": [
    {"level": 0, "definition": "拒绝还款", "boundary": "...", "example_turns": [...]},
    {"level": 1, "definition": "否认欠款", "boundary": "...", "example_turns": [...]},
    ...
    {"level": 4, "definition": "同意还款", "boundary": "...", "example_turns": [...]}
  ]
}
```

**Output 2**: `/src/f001_schema_alignment/output_labeled.py` (per-turn state labels)

> **Note**: This is an F000-produced artifact. It is written under the `f001_schema_alignment/` directory because F001 consumes it immediately, but it is generated by F000's labelling pass, not by F001.

493 of 805 turns are labeled with `state` dicts. Customer turns get `state: {facts: [...], emotions: [...], willingness: "..."}`. Collector turns get `state: {action: "..."}`. Unlabeled turns (filler like "嗯", "对", "好") omit `state`.

```python
# output_labeled.py excerpt
results = [
  {
    "call_id": "2317941550352385028",
    "response": {
      "dialog": [
        {"role": "催收员", "text": "唉，您好，请问是……喂，您好，请问是。", "state": {"action": "greeting"}},
        {"role": "客户", "text": "喂。"},  # unlabeled — filler
        {"role": "客户", "text": "我想问一下……整个账单分期……", "state": {"facts": ["request_installment"], "willingness": "conditional"}},
        ...
      ]
    }
  },
  ...
]
```

### Step 1.3: F001 — Schema Alignment

#### What this does

Maps the 31 raw records from the collection-system schema to a SOP-aligned schema with `turns_annotated`, `reward`, `state_transitions`, and a derived `context` constraint dict. Carries F000's state labels into each turn (493/805 labeled) so the aligned schema is a superset of prior outputs, not a lossy transformation.

#### Design considerations & decisions

- **ADR-006**: Map 27 raw Chinese `customer_info` fields → 21 typed English `context` fields (boolean bitmask fields + numeric/categorical fields). Expanded 9→21 fields on 2026-06-22.
- **ADR-007**: Carry F000 state labels into `turns_annotated` — aligned schema is a superset, not lossy; preserves data lineage.
- **ADR-008**: Output format is a `.py` file with `results = [...]` for consistency with the existing pipeline (loaded via `importlib`); JSON would break downstream loading.
- **Review Note (resolved)**: Include F000 state labels in `turns_annotated`.

**Input**: `/data/matched_data.jsonl` + `state_keywords.json` + `output_labeled.py`

**Process**: Parse raw `dialog` string into structured turns. **Carry F000 state labels from `output_labeled.py` into `turns_annotated`** (ADR-007: aligned schema is a superset of prior outputs, not a lossy transformation). Derive `context` constraint dict from `customer_info` Chinese fields (ADR-006: 21 fields mapped).

**Output**: `/src/f001_schema_alignment/output_aligned.py`

```python
results = [
  {
    "call_id": "2317941550352385028",
    "cust_no": "0100252354",
    "call_date": "20260506",
    "coll_user_id": "SX17625",
    "mob_typ": "M1",
    "talk_time": "613",
    "plan_evaluation": "| 类型 | 执行情况 | ...",
    "customer_info": { ... },  # preserved verbatim from source
    "turns_annotated": [
      {
        "turn_index": 0,
        "role": "催收员",
        "text": "唉，您好，请问是……喂，您好，请问是。",
        "state": {"action": "greeting"}
      },
      {
        "turn_index": 1,
        "role": "客户",
        "text": "喂。"
        # no state — unlabeled turn
      },
      {
        "turn_index": 7,
        "role": "客户",
        "text": "我想问一下，唉，譬如说，呃，不是说我是想整个账单分期，然后呃，分期完之后，这个信用卡就没有了，就要取消了，是这个意思吗？",
        "state": {
          "facts": ["request_installment"],
          "willingness": "conditional"
        }
      },
      {
        "turn_index": 11,
        "role": "客户",
        "text": "这样子……那那你还有其他的办法吗？",
        "state": {
          "emotions": ["disappointment"],
          "willingness": "negotiating"
        }
      },
      {
        "turn_index": 12,
        "role": "催收员",
        "text": "嗯，其他办法，这边的话就是说，建议你去还最低还款，26463块钱。",
        "state": {"action": "plan_proposal"}
      }
    ],
    "reward": null,             # filled by F003
    "state_transitions": [],    # filled later
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
  },
  ...  # 31 records total
]
```

**Key**: `turns_annotated[].state` labels are carried from F000's `output_labeled.py` per ADR-007 (493/805 turns labeled; unlabeled turns are filler like "嗯", "对", "好"). `context` is derived from `customer_info` Chinese fields → 21 English fields per ADR-006.

### Step 1.4: F003 — Reward Labeling

#### What this does

Assigns a binary reward R ∈ {0,1} per conversation via LLM detection of repayment-commitment triggers in the final turns, with counterfactual verification crediting the preceding collector action. Output: 6 R=1, 25 R=0 of 31 records. 


#### Design considerations & decisions

- **ADR-010**: Reward labeling via LLM with counterfactual verification — manual labeling doesn't scale; LLM + counterfactual + cross-validation against `plan_evaluation` gives consistency and auditability.
- **Review Note (resolved)**: since the counterfactual verification outputs a single action turn which does not really convey useful information in a glance, the success may be credited to the strategy used throughout the conversation. `reward_action_credit` includes an `explanation` field (<100 words) describing the causal flow from trigger to credited collector action.

**Input**: `output_aligned.py`

**Process**: LLM determines R ∈ {0, 1} per conversation. Detects repayment commitment triggers in final turns, performs counterfactual verification.

**Output**: `/src/f003_reward_labeling/output_rewarded.py`

Same structure as `output_aligned.py`, but:
- `reward` is now ∈ {0, 1} (was `null`)
- `reward_action_credit` added for R=1 records
- `reward_evidence` added for R=1 records

```python
# R=1 record example:
{
  "call_id": "2320459500460373224",
  "reward": 1,
  "reward_evidence": {
    "trigger_text": "嗯，好的，嗯，好好好",
    "trigger_turn_index": 38
  },
  "reward_action_credit": {
    "turn_index": 38,
    "role": "客户",
    "action": "agree_to_pay",
    "text": "嗯，好的，嗯，好好好",
    "explanation": "Customer showed financial hardship..."
  },
  ...  # all other fields same as output_aligned
}

# R=0 record example:
{
  "call_id": "2317941550352385028",
  "reward": 0,
  "reward_action_credit": None,
  ...
}
```

**Stats**: 31 records total, 6 with R=1, 25 with R=0.

### Step 1.5: F004 — Decision Tree Construction

#### What this does

Builds a collector decision tree (309 nodes, 782 sentences, max depth 17) where nodes are collector action points, branches are customer facts/emotions, and willingness is a per-sentence label. Conversations are decomposed into segments of (customer branch key → collector sentences), walked fact-by-fact to create single-key nodes, then transformed (action splitting, redundant fact/emotion collapse, node-identity dedup) into a DAG.

#### Design considerations & decisions

- **ADR-011**: Nodes = collector action points, branches = customer (facts, emotions), willingness = sentence label. Eliminated chain structure (single-child ratio 14.4%). Consolidated `initial_contact` root + `normal_end` / `abrupt_end` terminals.
- **ADR-012**: `collector_action` field on sentence entries — UI display + O(1) action filtering without traversing to parent.
- **ADR-015**: Local tree building (no global node reuse) — global reuse broke path continuity; match only against `current_node` children.
- **ADR-016**: Fact-by-fact walking — walk each fact/emotion one at a time, creating single-key nodes; eliminates composite-node bugs.
- **ADR-017**: Action node splitting — force-split pools into `a:xxx` children for fact/emotion parents; uniform `fact→emotion→action→sentences` structure.
- **ADR-018 (superseded by ADR-022)**: Redundant fact collapse with `inherited_facts` propagation.
- **ADR-019**: `state=None` collector turns captured without synthetic other` label (58 turns, 14.5%) — merged into parent pool.
- **ADR-021**: Node identity dedup — identity = `(inherited_facts, inherited_emotions, branch_key)`; DAG with cycle protection via `_is_ancestor`.
- **ADR-022**: Redundant emotion collapse — extends ADR-018 to collapse `anger → anger` nested emotion paths.
- **ADR-023**: Sentence pool dedup at transform boundaries — `_dedup_pool` by `script_text` after every `.extend()`.
- **Willingness as sentence label, not branch key**: same (facts, emotions) = same decision point regardless of willingness.
- **Segment-based extraction**: each conversation decomposed into (customer branch key → collector sentences), not individual turns.
- **LLM-guided collector turn merging**: merge fragmented consecutive collector turns before segment extraction; hard limit `MAX_MERGED_WORDS=150`.
- **Start/end node model**: exactly 1 opening root + 2 consolidated end nodes as direct children of root; clean vertical structure.

**Input**: `output_rewarded.py`

**Process**: Extract state-transition paths from annotated conversations, merge identical/near-identical state sequences, accumulate historical collector sentences at each node.

**Output**: `/src/f004_decision_tree/decision_tree.json`

Tree structure (309 nodes, 782 sentences):

```json
{
  "state_id": "initial_contact",
  "branch_key": {},
  "inherited_facts": [],
  "inherited_emotions": [],
  "sentence_pool": [
    {
      "script_text": "嗯嗯，嗯对。",
      "script_id": "2321972230428936547_t10",
      "source_call_ids": ["2321972230428936547"]
    }
  ],
  "children": [
    {
      "state_id": "a:closure",
      "branch_key": {"action": "closure"},
      "inherited_facts": [],
      "inherited_emotions": [],
      "sentence_pool": [...],
      "children": []
    },
    {
      "state_id": "f:request_installment",
      "branch_key": {"facts": ["request_installment"]},
      "inherited_facts": [],
      "inherited_emotions": [],
      "sentence_pool": [...],
      "children": [
        {
          "state_id": "a:information",
          "branch_key": {"action": "information"},
          "inherited_facts": ["request_installment"],
          "inherited_emotions": [],
          "sentence_pool": [...],
          "children": []
        },
        {
          "state_id": "e:disappointment",
          "branch_key": {"emotions": ["disappointment"]},
          "inherited_facts": ["request_installment"],
          "inherited_emotions": [],
          "sentence_pool": [],
          "children": [
            {
              "state_id": "a:plan_proposal",
              "branch_key": {"action": "plan_proposal"},
              "inherited_facts": ["request_installment"],
              "inherited_emotions": ["disappointment"],
              "sentence_pool": [...],
              "children": []
            },
            {
              "state_id": "f:ability_to_pay",
              "branch_key": {"facts": ["ability_to_pay"]},
              "inherited_facts": ["request_installment"],
              "inherited_emotions": ["disappointment"],
              "sentence_pool": [],
              "children": [...]
            }
          ]
        }
      ]
    }
  ]
}
```

**Key**: `branch_key` is a dict with one key — either `"facts"`, `"emotions"`, or `"action"` — containing the state group that led to this branch. `inherited_facts` accumulates facts from ancestor nodes. `inherited_emotions` accumulates emotions from ancestor nodes. The `state` label on customer turns may also include a `willingness` field (e.g. `"conditional"`, `"negotiating"`, `"strong"`) from F000's willingness levels — willingness is tracked in conversation state but is not used in the node key or tree structure.

### Step 1.6: F005 — Context Scoring + Embedding + Database Load

#### What this does

Tags each tree sentence with a 10-bit `bg_bitmask` (customer profile constraints) for soft-label, computes two quality scores (HWR = Laplace-smoothed blended win rate; SAS = char-bigram TF-IDF cosine within pool), extracts the ~100-word conversation context preceding each script, embeds it via bge-m3 (1024-dim), and loads nodes + sentences + taxonomy into PostgreSQL.

#### Design considerations & decisions

- **ADR-020**: 10-bit bitmask for soft scoring; intersection merge for multi-source sentences (conservative — only constraints in ALL source conversations are set); Laplace-smoothed HWR; char-bigram TF-IDF SAS (numpy only, no external API). Expanded 5→10 bits on 2026-06-22. Soft scoring replaced hard filter on 2026-06-29.
- **ADR-024**: bge-m3 via Ollama replaces char-ngram TF-IDF for semantic similarity — captures meaning ("没钱" ≈ "经济困难"); local/no-cost/offline; pgvector hybrid; unified ranking replaces dual-strategy.
- **HWR with node-level aggregation**: sentence-level HWR unreliable for sentences in only 1-2 calls; blend `weight * sentence_hwr + (1-weight) * node_hwr` where `weight = n/(n+2)`.
- **UC and CSI deferred**: `uplift_score = 0`, `csi = 0` with `deferred: true` — require causal analysis unavailable at 31-record scale.
- **F007 design**: Ollama for local embeddings (no per-call cost); OpenAI-compatible API (reuse `openai` client); Python-side ranking (`bg_boost` needs JSONB dict comparison); pgvector for hybrid vector+bitmask+FTS in one query; optional embedding in `score_tree.py` (backward compat when `db=None`).

**Input**: `decision_tree.json` + `output_aligned.py` + `output_rewarded.py`

**Process** (per sentence in every node's `sentence_pool`):

1. **Bitmask encoding**: Extract `bg_constraints` from source conversation's `customer_info` → encode as 10-bit integer `bg_bitmask_int`
2. **HWR/win_rate**: Compute historical win rate: `(wins + 1) / (total + 2)` where wins = count of R=1 in `source_call_ids`
3. **SAS**: Compute Script Analogy Score via char bigram TF-IDF cosine similarity within pool (no external API — ADR-020)
4. **Conversation context extraction**: Extract the ~100 words preceding this script in the source conversation → `conversation_context` string
5. **Embedding**: `embed(conversation_context)` via bge-m3 embedding model served by Ollama → 1024-dim float32 vector → `embedding` column (ADR-024)
6. **Full-text vector**: `to_tsvector('simple', script_text)` → `script_tsv` column

**Output**: `/src/f005_context_scoring/decision_tree_scored.json` (backward compat) + PostgreSQL

Each sentence in the scored tree has these exact fields:

```json
{
  "script_text": "嗯嗯，嗯对。",
  "script_id": "2321972230428936547_t10",
  "source_call_ids": ["2321972230428936547"],
  "customer_willingness": null,
  "fact_context": ["prior_contact_attempt"],
  "bg_constraints": {
    "has_auto_loan": false,
    "has_mortgage": false,
    "has_negotiation_history": false,
    "social_insurance_stable": false,
    "credit_rating_good": false,
    "card_restricted": false,
    "is_cash_out_customer": false,
    "has_complaint_history": false,
    "has_legal_tools": false,
    "is_negotiation_brain_customer": false
  },
  "bg_bitmask": {
    "has_auto_loan": 0,
    "has_mortgage": 0,
    "has_negotiation_history": 0,
    "social_insurance_stable": 0,
    "credit_rating_good": 0,
    "card_restricted": 0,
    "is_cash_out_customer": 0,
    "has_complaint_history": 0,
    "has_legal_tools": 0,
    "is_negotiation_brain_customer": 0
  },
  "bg_bitmask_int": 0,
  "bg_background": {
    "age": "48",
    "gender": "男",
    "education": "未填",
    "industry": "医疗卫生",
    "is_cash_out": "非套现客户",
    "is_restricted": "可正常使用卡片",
    "complaint_history": "客户历史没有重渠投诉",
    "external_debt_institutions": "无外部共债机构",
    "interest_ratio": "0%",
    "installment_ratio": "0%",
    "legal_tools": "无可用的法务工具",
    "negotiation_brain": "N"
  },
  "win_rate": 0.333,
  "sas": 0.0,
  "uplift_score": 0,
  "csi": 0,
  "deferred": true,
  "conversation_context": "唉，喂，您好。招商银行信用卡中心，请问是<PERSON>女士吗？ 您好，对。...",
  "embedding": [0.012, -0.034, 0.078, ...]  // 1024-dim bge-m3 via Ollama
}
```

**PostgreSQL load** (nodes + sentences + taxonomy_keywords):

```sql
-- Nodes
INSERT INTO nodes (state_id, path_signature, branch_key, parent_id, depth)
VALUES ('initial_contact', '', '{}'::jsonb, NULL, 0);

INSERT INTO nodes (state_id, path_signature, branch_key, parent_id, depth)
VALUES ('f:request_installment', 'request_installment',
        '{"facts":["request_installment"]}'::jsonb, 1, 1);

-- Sentences (with embedding and tsvector)
INSERT INTO sentences (script_id, node_id, script_text, bg_bitmask_int,
                        win_rate, sas, bg_background, conversation_context,
                        embedding, script_tsv)
VALUES (
  '2321972230428936547_t10', 1, '嗯嗯，嗯对。', 0,
  0.333, 0.0,
  '{"age":"48","gender":"男","industry":"医疗卫生",...}'::jsonb,
  '唉，喂，您好。招商银行信用卡中心...',
  '[0.012, -0.034, 0.078, ...]'::vector(1024),
  to_tsvector('simple', '嗯嗯，嗯对。')
);

-- Taxonomy keywords (for F008 keyword-fallback state extraction)
INSERT INTO taxonomy_keywords (group_name, category, keyword, frequency)
VALUES ('financial_hardship', 'facts', '最近经济压力有点大', 29),
       ('financial_hardship', 'facts', '经济困难', 29),
       ('request_installment', 'facts', '整个账单分期', 6),
       ...;
```

**In-memory node index** (loaded at API startup from `nodes` table):

```python
# Key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
# Value = list of node_ids sharing the same key (for pool aggregation)
node_index = {
  ((), (), ()):                                                      [1],     # root (initial_contact)
  ((), ("closure",), ()):                                            [2],     # a:closure (no inherited emotions)
  ((), ("empathy",), ()):                                            [3],     # a:empathy
  ((), ("greeting",), ()):                                           [4],     # a:greeting
  (("request_installment",), (), ()):                                [5],     # f:request_installment
  (("request_installment",), ("information",), ()):                  [6],     # f:request_installment → a:information
  (("request_installment",), ("disappointment",), ()):               [7],     # f:request_installment → e:disappointment
  (("request_installment",), ("plan_proposal",), ("disappointment",)): [8],  # ... → a:plan_proposal (inherited: disappointment)
  # ...301 unique keys → 309 nodes total
}
# Maps (facts_tuple, bk_tuple, emotions_tuple) → [node_ids] for O(1) lookup + pool aggregation
# inherited_emotions is required: 31 key collisions without it (same facts+bk, different emotional context)
```

---

## Phase 2: Retrieve (online, per API call)

> **Feature mapping**: Infrastructure (PostgreSQL + pgvector, bge-m3 embeddings, DeepSeek LLM) → **F007**. Vector retrieval integration (F005 embed load + F006 vector ranking) → **F007b**. State extraction (Step 2.1) → **F008**. REST + Socket.IO API (endpoint below) → **F009**. Steps 2.2–2.7 retrieval/ranking logic lives in **F006** (modified by F007b).

### API Endpoint (F009)

#### What this does

Exposes the recommendation pipeline over two interfaces: `POST /recommend` (REST, single-turn — the caller manages conversation state and passes it back each call) and a Socket.IO session interface (server manages state accumulation automatically across `start_session` / `customer_turn` / `collector_turn` / `end_session` events). Both run the same 7-step pipeline.

#### Design considerations & decisions

- **F009**: FastAPI chosen (already in `pyproject.toml`). Socket.IO added for stateful session management so the call platform doesn't have to track conversation state client-side.
- **No LLM in ranking hot path** beyond the single F008 state-extraction call (ADR-009 eliminated the second LLM pass).
- **Fallback hierarchy**: 5 levels — path signature miss → root; LLM fail → keyword; embed fail → win_rate+sas only; all exhausted → 404. Bitmask is now a soft ranking signal, not a filter. See [Fallback Hierarchy](#fallback-hierarchy).

```
POST /recommend
```

### Input Schema

```json
{
  "customer_utterance": "我现在真的没钱还，能不能分期",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还",
  "conversation_state": {
    "branch_key": {"facts": ["financial_hardship"]},
    "inherited_facts": [],
    "inherited_emotions": [],
    "willingness": null
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

**Field descriptions:**
- `customer_utterance`: The customer's most recent turn text
- `conversation_context`: Aggregated text of the past ~100 words of dialog (both customer and collector turns)
- `conversation_state`: **Path-structured** state `{branch_key, inherited_facts, inherited_emotions, willingness}` mirroring the tree's node identity (ADR-021). Caller passes back the `conversation_state` from the previous API response. `branch_key` is the most recent branching decision; `inherited_facts`/`inherited_emotions` accumulate from ancestors. Note: F002 (LLM State Extraction) was eliminated per ADR-009; online extraction (Step 2.1) is the only LLM call in the hot path (plus at most one relabel call per ADR-026).
- `context`: Customer profile from `customer_info`, transformed to the `context` dict format (ADR-006: 21 fields mapped from Chinese `customer_info`)

---

### Step 2.1: State Extraction (LLM-first) — F008

#### What this does

Extracts the customer's state (facts, emotions, actions, willingness) from their utterance using DeepSeek LLM as the primary path (**open-set** for facts/emotions per ADR-026, **closed-set** for willingness), then normalizes extracted labels through a synchronous relabel pipeline. PostgreSQL tsvector keyword search is the fallback when the LLM fails.

#### Design considerations & decisions

- **ADR-026**: Open-set extraction for facts/emotions — the LLM extracts whatever labels best describe the utterance, unconstrained by a predefined list. Willingness remains closed-set (6 ordered levels per ADR-005).
- **Synchronous relabel pipeline** (ADR-026): each extracted label is checked against `*_descriptions` (canonical set) → `*_relabeled` CSV (existing mapping) → if no mapping, `llm_relabel` runs synchronously to generate one and appends it to `*_relabeled`. Worst-case latency ~2x on novel labels; rare in steady state as the cache grows.
- **ADR-009**: Eliminated F002 (a second offline LLM state-extraction pass) — online extraction + at most one relabel call is the only LLM work in the hot path.
- **F008**: LLM-first with keyword fallback — DeepSeek for semantic extraction, tsvector keyword scan via `taxonomy_keywords` table when LLM unavailable.
- **State accumulation rules**: path-structured (see Step 2.2); willingness is a scalar (overwrite with latest non-null).

**Primary path**: DeepSeek LLM call

```
Prompt to DeepSeek (ADR-026: open-set for facts/emotions, closed-set for willingness):
---
Extract the customer's state from the following utterance.

Extract facts and emotions FREELY — use whatever labels best describe the
customer's situation and emotional state. Do NOT limit yourself to a predefined
list. Use snake_case English labels (e.g. "financial_hardship",
"request_installment", "income_delay").

WILLINGNESS (pick exactly one or null):
- resistant: refuses to pay
- weak: acknowledges but resists
- conditional: will pay if conditions met
- negotiating: actively discussing payment
- cooperative: willing to cooperate
- strong: agrees to pay

Customer utterance: "我现在真的没钱还，能不能分期"

Return JSON: {"facts": [...], "emotions": [...], "actions": [...], "willingness": "..." or null, "confidence": 0.0-1.0}
---

DeepSeek response (raw, pre-relabel):
{
  "facts": ["request_installment"],
  "emotions": ["pleading"],
  "willingness": "conditional",
  "confidence": 0.9
}

→ Relabel pipeline (synchronous, ADR-026):
  1. "request_installment" ∈ facts_descriptions? → check facts_relabeled.csv → maps to "installment_request"
  2. "pleading" ∈ emotions_descriptions? → check emotions_relabeled.csv → maps to "negotiation"
  3. Final: {"facts": ["installment_request"], "emotions": ["negotiation"], "willingness": "conditional"}
```

**Fallback path** (only if LLM fails): PostgreSQL tsvector keyword search

```sql
SELECT group_name, category
FROM taxonomy_keywords
WHERE tsv @@ to_tsquery('simple', '没钱 & 分期')
LIMIT 10;
```

**Output of this step:**
```json
{
  "facts": ["request_installment"],
  "emotions": ["pleading"],
  "actions": [],
  "willingness": "conditional",
  "confidence": 0.9,
  "method": "llm"
}
```

**Latency**: ~800-1200ms (extraction LLM) + 0ms (relabel cache hit) | ~1600-2400ms (novel label, relabel LLM) | ~5ms (keyword fallback)

---

### Step 2.2: State Accumulation

#### What this does

Merges the new extraction into the existing **path-structured** conversation
state: `{branch_key, inherited_facts, inherited_emotions, willingness}`. The
state mirrors the tree's own node structure (ADR-021) — `branch_key` is the
most recent branching decision, `inherited_facts`/`inherited_emotions`
accumulate from ancestors. This unifies online retrieval with offline tree
building (ADR-015): both walk paths.

#### Design considerations & decisions

- **ADR-021 / ADR-015**: Path-structured state mirrors tree node identity
  `(inherited_facts, branch_key, inherited_emotions)`. Online retrieval walks
  the same path structure the tree was built with.
- **Step 2.3 becomes a no-op**: the state *is* the key, not derived from it.
- **Insertion order**: preserved within `inherited_facts`/`inherited_emotions`
  for F010 trace readability — **cosmetic, not functional** (the node key is
  `tuple(sorted(...))`, permutation-insensitive, so
  `(bankrupt, angry, unemployed)` and `(bankrupt, unemployed, angry)` produce
  the same key).
- **Willingness as scalar**: overwrites (not appended) — represents current
  intent, not history.

**Accumulation logic:**
- New fact → promote current `branch_key` fact to `inherited_facts`, set `branch_key = {"facts": [new_fact]}`
- New emotion → promote current `branch_key` to inherited, set `branch_key = {"emotions": [new_emotion]}`
- New action → set `branch_key = {"action": new_action}` (actions are the current move, not accumulated)
- Willingness → overwrite if non-null
- Deduplicate: if a fact/emotion already in `inherited_facts`/`inherited_emotions` ∪ `branch_key`, skip

```
existing_state = {
  branch_key: {"facts": ["financial_hardship"]},   ← from turn 2
  inherited_facts: [],
  inherited_emotions: [],
  willingness: null
}

new_extraction = {
  facts: ["request_installment"],    ← from this turn
  emotions: ["pleading"],
  actions: [],
  willingness: "conditional"
}

merged_state = {
  branch_key: {"emotions": ["pleading"]},            ← latest branch
  inherited_facts: ["financial_hardship", "request_installment"],
  inherited_emotions: [],
  willingness: "conditional"
}
```

**Latency**: <1ms

---

### Step 2.3: Node Key Computation

#### What this does

**No-op** — the path-structured state *is* the node identity key. The
`(inherited_facts, branch_key_values, inherited_emotions)` triple (ADR-021) is
read directly from the state, not derived from flat lists.

#### Design considerations & decisions

- **ADR-021**: Node identity = `(inherited_facts, inherited_emotions,
  branch_key)` — the key that makes lookup O(1) and permutation-insensitive.
- **ADR-022 / F006**: `inherited_emotions` is required in the key — without
  it, 31 key collisions occur (e.g. `a:closure` under `['disappointment']`
  vs `['anger']` must not aggregate).
- **Willingness excluded from key**: tracked in conversation state but not
  used for node matching (it's a sentence label, per ADR-011).

```
key = (tuple(sorted(facts)), tuple(sorted(branch_key_values)), tuple(sorted(emotions)))

merged_state = {
  facts: ["financial_hardship", "request_installment"],
  emotions: ["pleading"],
  actions: [],
  willingness: "conditional"
}

key = (("financial_hardship", "request_installment"), (), ("pleading",))
```

**Latency**: <1ms

---

### Step 2.4: Node Lookup (subset-match, with aggregation)

#### What this does

Looks up nodes by the path-structured state's label set. On exact match,
aggregates all matching nodes' sentence pools. On miss, falls back through
**best subset match** (drop emotions first, then facts), pooling all nodes at
the largest matching subset size. Keeps **descend** for the empty-pool case.

#### Design considerations & decisions

- **Best subset match** (replaces key-drop): if 5 labels and no perfect match, find 4-label matches (position-independent), then 3, 2, 1. Pool all nodes matching at the largest subset size, capped at N=50 candidates.
- **Drop emotions first, then facts**: emotional context is relaxed before fact specificity — facts define *what situation*, emotions define *how they feel*; in fallback, preserve the situation longer. This is the inverse of ADR-022's build-time concern (which kept emotions in the key to avoid aggregating different emotional contexts). At retrieval fallback, we accept that relaxation deliberately.
- **Descend (kept for empty-pool)**: if matched nodes have empty pools but have children, BFS down tree to nearest non-empty pools, −0.05 per level. This handles a different case than subset match (empty pool, not key miss).
- **F006**: Aggregate all sibling pools — avoids premature filtering by tree position.

```python
# Exact match: label set {financial_hardship, request_installment, pleading}
nodes = label_set_index[frozenset({"financial_hardship", "request_installment", "pleading"})]
# → [node_42, node_58]  — pool all
```

**Fallback cascade** (if exact label-set miss):

1. **Best subset match — drop emotions first**: try all (n-1)-emotion subsets, then (n-2), ... then all emotions dropped, then drop 1 fact, 2 facts, ... Pool all nodes matching at the first successful subset size (cap N=50). Confidence: `1.0 − 0.1 × n_dropped`.
2. **Descend fallback**: If matched nodes have empty pools but have children, walk DOWN the tree (BFS) to nearest descendants with non-empty pools. All siblings at the same depth are included. Each level: −0.05 confidence.
3. **Root fallback**: If all subsets exhausted, use root node (`initial_contact`). 0.2 confidence.

**Latency**: <1ms (label-set lookup) | O(C(n,k) × keys) with subset fallback

---

### Step 2.5: Candidate Retrieval + Bitmask Filter (PostgreSQL)

#### What this does

Fetches candidate sentences from PostgreSQL by `node_id`, then scores each by bitmask overlap: `bitmask_score = matched_bits / required_bits`. No sentences are filtered out — partial matches rank lower via the `bitmask_score` ranking weight (0.20). Confidence is penalized proportionally for mismatches.

#### Design considerations & decisions

- **ADR-020 (updated)**: Bitmask as soft ranking signal — partial matches are demoted, not eliminated. A sentence with bitmask 0 scores 1.0 (no constraints). A sentence with 4/5 required bits matching scores 0.80.

**Bitmask encoding** from `context` dict:

```
Bit positions (from scoring_metrics.py BITMASK_FIELDS):
  bit 0: has_auto_loan
  bit 1: has_mortgage
  bit 2: has_negotiation_history
  bit 3: social_insurance_stable
  bit 4: credit_rating_good
  bit 5: card_restricted
  bit 6: is_cash_out_customer
  bit 7: has_complaint_history
  bit 8: has_legal_tools
  bit 9: is_negotiation_brain_customer

For our sample customer:
  has_mortgage=true → bit 1 set
  all others false
  query_bitmask = 0b0000000010 = 2
```

**Bitmask scoring logic**: `compute_bitmask_score(sentence_bitmask, query_bitmask)`

```
if sentence_bitmask == 0:  return 1.0   # no requirements → perfect match
if query_bitmask == 0:     return 0.5   # no query context → neutral
matched_bits = popcount(sentence_bitmask & query_bitmask)
required_bits = popcount(sentence_bitmask)
return matched_bits / required_bits
```

Examples:
- Sentence `bg_bitmask_int=0` (no constraints) → score 1.0
- Sentence `bg_bitmask_int=2` (requires `has_mortgage`), query has bit 1 → 1/1 = 1.0
- Sentence `bg_bitmask_int=18` (requires `has_mortgage` + `credit_rating_good`), query has bit 1 only → 1/2 = 0.50
- Sentence `bg_bitmask_int=31` (requires 5 bits), query has 3 of them → 3/5 = 0.60

**Confidence penalty**: If top result has `bitmask_score < 1.0`, confidence is reduced by `(1.0 - bitmask_score) × bitmask_mismatch_penalty` (default 0.1).

**Ranking**: `bitmask_score` is the 5th ranking weight alongside `win_rate`, `vec_score`, `sas`, and `bg_boost`:

```
final_score = 0.35 × win_rate
            + 0.25 × vec_score
            + 0.10 × sas
            + 0.10 × bg_boost
            + 0.20 × bitmask_score
```

**Latency**: ~2-5ms

---

### Step 2.6: Vector Semantic Match (pgvector)

#### What this does

Embeds the query conversation context with bge-m3 (1024-dim), then computes cosine similarity against each candidate's stored embedding via pgvector. Can be done as a single SQL query (combining steps 2.5+2.6+2.7) or fetch + compute in Python (needed for `bg_boost`).

#### Design considerations & decisions

- **ADR-024**: bge-m3 via Ollama replaces char-ngram TF-IDF for semantic similarity — captures meaning, local/no-cost/offline, 1024-dim.
- **F007**: pgvector HNSW index for O(log N) approximate KNN; hybrid vector+bitmask+FTS in one PostgreSQL query.

**Step 2.6.1**: Embed the query conversation context

```python
query_vec = embed_single("招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还")
# → [0.015, -0.042, 0.091, ...]  (1024-dim float32, bge-m3 via Ollama)
```

**Step 2.6.2**: Compute cosine similarity against each candidate's stored `embedding`

**Option A — Single SQL query** (combines Steps 2.5 + 2.6 + 2.7):

```sql
SELECT script_id, script_text, win_rate, sas, bg_bitmask_int, bg_background,
       1 - (embedding <=> $query_vec) AS vec_score,
       CASE WHEN bg_bitmask_int = 0 THEN 1.0
            WHEN $query_bitmask = 0 THEN 0.5
            ELSE popcount(bg_bitmask_int & $query_bitmask)::real / popcount(bg_bitmask_int)::real
       END AS bitmask_score
FROM sentences
WHERE node_id = ANY($node_ids)
ORDER BY (0.35 * win_rate + 0.25 * (1 - (embedding <=> $query_vec)) + 0.10 * sas + 0.20 * bitmask_score) DESC
LIMIT 1;
```

**Option B — Fetch candidates, compute in Python** (more flexible for `bg_boost`):

Fetch candidates with embeddings from PG, compute `vec_score` + `bg_boost` + `final_score` in Python.

**Latency**: ~50-100ms (bge-m3 embed via Ollama) + ~2ms (pgvector cosine)

---

### Step 2.7: Rerank (Weighted Fusion)

#### What this does

Ranks the filtered candidates by unified weighted fusion: `0.40·win_rate + 0.30·vec_score + 0.15·sas + 0.15·bg_boost`. Returns the top-1 script. `bg_boost` is a soft profile-match bonus computed in Python (industry, education, debt range, age).

#### Design considerations & decisions

- **ADR-024 / F006**: Unified weighted fusion replaces the previous dual-strategy (`limited`/`full`) switch — vector similarity provides a meaningful semantic signal at any data scale, making the strategy switch unnecessary.
- **F006**: `win_rate` (0.40) is the strongest signal — proven effectiveness; `vec_score` (0.30) — semantic relevance; `sas` (0.15) — intra-pool redundancy avoidance (tiebreak); `bg_boost` (0.15) — profile personalization (soft, not a hard filter).
- **F007**: Python-side ranking because `bg_boost` requires JSONB dict comparison not expressible in SQL (~1ms tradeoff for flexibility).
- **Embedding fallback**: if embedding unavailable, set `vec_score = 0`, redistribute weight to `win_rate`.

**Signals:**

| Signal | Source | Range | Meaning |
|---|---|---|---|
| `win_rate` | HWR from `reward` labels in `output_rewarded.py` | [0, 1] | Historical effectiveness |
| `vec_score` | pgvector cosine similarity | [0, 1] | Semantic relevance to current conversation |
| `sas` | Char bigram TF-IDF cosine within pool | [0, 1] | Script diversity |
| `bg_boost` | Profile match heuristic | [0, 0.12] | Customer profile similarity bonus |

**Weights:**

```python
RANKING_WEIGHTS = {
    "win_rate": 0.40,
    "vec_score": 0.30,
    "sas": 0.15,
    "bg_boost": 0.15,
}
```

**bg_boost computation** (from `retrieval_ranking.py:compute_bg_boost`):

```python
def compute_bg_boost(sentence_bg, query_bg):
    boost = 0.0
    if sentence_bg["industry"] == query_bg["industry"]:
        boost += 0.05
    if sentence_bg["education"] == query_bg["education"]:
        boost += 0.02
    if abs(int(sentence_bg.get("age", 0)) - int(query_bg.get("age", 0))) <= 10:
        boost += 0.02
    s_debt = safe_int(sentence_bg.get("total_debt", 0))
    q_debt = safe_int(query_bg.get("total_debt", 0))
    if s_debt > 0 and q_debt > 0 and max(s_debt, q_debt) / min(s_debt, q_debt) <= 1.5:
        boost += 0.03
    return boost
```

**Final score:**

```
final_score = 0.40 × win_rate + 0.30 × vec_score + 0.15 × sas + 0.15 × bg_boost
```

**Unified weighted fusion** (ADR-024: dual strategy deleted, single unified path):

```python
RANKING_WEIGHTS = {
    "win_rate": 0.35,
    "vec_score": 0.25,
    "sas": 0.10,
    "bg_boost": 0.10,
    "bitmask_score": 0.20,
}

def recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
    nodes = lookup_by_key(key, node_index)
    pool = aggregate_pools(nodes)
    for s in pool:
        s["bitmask_score"] = compute_bitmask_score(s.bg_bitmask_int, query_bitmask)
    # vec_score computed via pgvector or bge-m3 embed + cosine
    bg_boost = compute_bg_boost(sentence_bg, query_bg)
    final_score = 0.35 * win_rate + 0.25 * vec_score + 0.10 * sas + 0.10 * bg_boost + 0.20 * bitmask_score
    return top_by_final_score(pool)
```

**Latency**: <1ms

---

### Step 2.8: Output

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
    "actions": [],
    "willingness": "conditional"
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

---

## Phase 3: Full Conversation Walkthrough

A 5-turn call using real data from call `2317941550352385028` (customer 0100252354, 专业性事务所, age 49).

### Turn 1: Initial contact

**Request:**
```json
POST /recommend
{
  "customer_utterance": "喂",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗",
  "conversation_state": {
    "facts": [],
    "emotions": [],
    "actions": [],
    "willingness": null
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

**Processing:**
1. LLM → `{facts: [], emotions: [], actions: [], willingness: null, confidence: 0.5, method: "llm"}`
2. State accumulation: `{facts: [], emotions: [], actions: [], willingness: null}` (nothing new)
3. Node key: `((), (), ())` → root
4. Node lookup: `node_index[((), (), ())]` → node_id=1 (`initial_contact`)
5. PG query: `SELECT ... WHERE node_id = 1 AND (bg_bitmask_int & 2) = bg_bitmask_int`
6. Vector match + rerank

**Response:**
```json
{
  "script_text": "嗯嗯，嗯对。",
  "script_id": "2321972230428936547_t10",
  "state_id": "initial_contact",
  "win_rate": 0.333,
  "vec_score": 0.75,
  "sas": 0.0,
  "final_score": 0.345,
  "confidence": 0.5,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": [],
    "emotions": [],
    "actions": [],
    "willingness": null
  },
  "ranking_weights": {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15},
  "fallbacks": [],
  "latency_ms": 900
}
```

---

### Turn 2: Customer reveals financial hardship

**Request:**
```json
POST /recommend
{
  "customer_utterance": "最近经济压力有点大，所以才会逾期",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗 对对对 告知逾期金额 客户说经济压力大",
  "conversation_state": {
    "facts": [],
    "emotions": [],
    "actions": [],
    "willingness": null
  },
  "context": { ... same ... }
}
```

**Processing:**
1. LLM → `{facts: ["financial_hardship"], emotions: [], actions: [], willingness: null, confidence: 0.95, method: "llm"}`
2. State accumulation: `{facts: ["financial_hardship"], emotions: [], actions: [], willingness: null}`
3. Node key: `(("financial_hardship",), (), ())`
4. Node lookup → node for `f:financial_hardship`
5. PG query + vector match + rerank

**Response:**
```json
{
  "script_text": "我理解您的困难，那您看能不能先还一部分呢？",
  "script_id": "s_fin_hard_1",
  "state_id": "financial_hardship",
  "win_rate": 0.60,
  "vec_score": 0.85,
  "sas": 0.70,
  "final_score": 0.610,
  "confidence": 0.95,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship"],
    "emotions": [],
    "actions": [],
    "willingness": null
  },
  "ranking_weights": {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15},
  "fallbacks": [],
  "latency_ms": 1050
}
```

---

### Turn 3: Customer requests installment, shows disappointment

**Request:**
```json
POST /recommend
{
  "customer_utterance": "我想问一下，整个账单分期，分期完之后信用卡取消，是这个意思吗？",
  "conversation_context": "... 告知逾期金额 客户说经济压力大 催收员建议先还一部分 客户请求分期 询问分期条件",
  "conversation_state": {
    "facts": ["financial_hardship"],
    "emotions": [],
    "actions": [],
    "willingness": null
  },
  "context": { ... same ... }
}
```

**Processing:** #jiani
1. LLM → `{facts: ["request_installment"], emotions: ["disappointment"], willingness: "conditional", confidence: 0.9, method: "llm"}`
2. State accumulation:
   - existing: `{facts: ["financial_hardship"], emotions: [], actions: [], willingness: null}`
   - new: `{facts: ["request_installment"], emotions: ["disappointment"], willingness: "conditional"}`
   - merged: `{facts: ["financial_hardship", "request_installment"], emotions: ["disappointment"], actions: [], willingness: "conditional"}`
3. Node key: `(("financial_hardship", "request_installment"), ("disappointment",), ())` — new emotion in branch_key, not yet inherited
4. Node lookup → nodes under `f:request_installment → e:disappointment` (aggregated pool)
5. PG query + vector match + rerank

**Response:**
```json
{
  "script_text": "嗯，其他办法，这边的话就是说，建议你去还最低还款...",
  "script_id": "2317941550352385028_t12",
  "state_id": "financial_hardship|disappointment|request_installment",
  "win_rate": 0.50,
  "vec_score": 0.82,
  "sas": 0.65,
  "final_score": 0.530,
  "confidence": 0.9,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["disappointment"],
    "actions": [],
    "willingness": "conditional"
  },
  "ranking_weights": {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15},
  "fallbacks": [],
  "latency_ms": 1080
}
```

---

### Turn 4: Collector proposes plan, customer shows ability to pay

**Request:**
```json
POST /recommend
{
  "customer_utterance": "我是有还款的能力，只是你一下子让我还20000多，可能就有点困难",
  "conversation_context": "... 客户请求分期 催收员建议最低还款 客户说明收入情况 有还款能力但一次性困难",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment"],
    "emotions": ["disappointment"],
    "actions": [],
    "willingness": "conditional"
  },
  "context": { ... same ... }
}
```

**Processing:**
1. LLM → `{facts: ["ability_to_pay", "income_statement"], emotions: [], actions: ["plan_proposal"], willingness: "negotiating", confidence: 0.85, method: "llm"}`
2. State accumulation:
   - merged: `{facts: ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"], emotions: ["disappointment"], actions: ["plan_proposal"], willingness: "negotiating"}`
3. Node key: `(("ability_to_pay", "financial_hardship", "income_statement", "request_installment"), ("plan_proposal",), ("disappointment",))`
4. Node lookup → deep node under `f:request_installment → e:disappointment → f:ability_to_pay → ...` (aggregated pool)
5. PG query + vector match + rerank

**Response:**
```json
{
  "script_text": "考虑到您目前的困难，我可以帮您申请减免...",
  "script_id": "2317941550352385028_t30",
  "state_id": "ability_to_pay|disappointment|financial_hardship|income_statement|plan_proposal|request_installment",
  "win_rate": 0.67,
  "vec_score": 0.90,
  "sas": 0.60,
  "final_score": 0.645,
  "confidence": 0.85,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"],
    "emotions": ["disappointment"],
    "actions": ["plan_proposal"],
    "willingness": "negotiating"
  },
  "ranking_weights": {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15},
  "fallbacks": [],
  "latency_ms": 950
}
```

---

### Turn 5: Customer agrees to pay

**Request:**
```json
POST /recommend
{
  "customer_utterance": "好的，好的，行。那我这边我给你想想办法啊",
  "conversation_context": "... 催收员提出减免方案 客户同意 表示会想办法还款",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"],
    "emotions": ["disappointment"],
    "actions": ["plan_proposal"],
    "willingness": "negotiating"
  },
  "context": { ... same ... }
}
```

**Processing:**
1. LLM → `{facts: [], emotions: ["cooperative"], actions: ["closure"], willingness: "strong", confidence: 0.8, method: "llm"}`
2. State accumulation:
   - `cooperative` is new emotion → appended
   - `closure` is new action → appended
   - `willingness` updated to `"strong"`
   - merged: `{facts: ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"], emotions: ["disappointment", "cooperative"], actions: ["plan_proposal", "closure"], willingness: "strong"}`
3. Node key: `(("ability_to_pay", "financial_hardship", "income_statement", "request_installment"), ("closure",), ("cooperative", "disappointment"))`
4. Node lookup → deepest matching node, or fallback
5. PG query + vector match + rerank

**Response:**
```json
{
  "script_text": "好的，那如果在明天您没有还进来的话，后续工作人员会再跟您沟通...",
  "script_id": "2317941550352385028_t50",
  "state_id": "ability_to_pay|closure|disappointment|cooperative|financial_hardship|income_statement|plan_proposal|request_installment",
  "win_rate": 0.83,
  "vec_score": 0.88,
  "sas": 0.55,
  "final_score": 0.722,
  "confidence": 0.8,
  "extraction_method": "llm",
  "conversation_state": {
    "facts": ["financial_hardship", "request_installment", "ability_to_pay", "income_statement"],
    "emotions": ["disappointment", "cooperative"],
    "actions": ["plan_proposal", "closure"],
    "willingness": "strong"
  },
  "ranking_weights": {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15},
  "fallbacks": [],
  "latency_ms": 920
}
```

---

## Tooling: F010 UI & Debug Endpoint

F010 provides a web UI replacing the `interactive.py` CLI, served via FastAPI
StaticFiles at `/ui` on the same server/port (no CORS). Three panels:

1. **REST mock panel** — Postman-style manual request builder for `POST /recommend`.
2. **Socket.IO session panel** — stateful session interface.
3. **Pipeline trace panel** — shows all 7 steps (input → output) for a single
   debug call, plus a sentence pool inspector.

A dedicated `POST /recommend/debug` endpoint returns the full per-step trace
data. Vanilla JS + CSS (no build step), CodeMirror 6 + Tailwind via CDN,
bundled Socket.IO client. See [F010](docs/features/F010-api-mock-system-status-ui.md)
and ADR-025.

---

## Latency Budget

| Step | Latency | Notes |
|---|---|---|
| State extraction (LLM) | 800-1200ms | DeepSeek API call (open-set, ADR-026) |
| Label normalization (relabel) | 0ms (cache hit) | `*_descriptions` / `*_relabeled` lookup |
| Label relabel (novel, sync LLM) | 800-1200ms | Conditional — only when label not in cache (ADR-026) |
| State accumulation | <1ms | In-memory set operations |
| Node key computation | <1ms | Sort + tuple |
| Node lookup + aggregation | <1ms | Hash map O(1) + pool merge |
| Candidate retrieval + bitmask scoring | 2-5ms | Indexed PG query + soft bitmask scoring |
| Vector embedding (query) | 50-100ms | bge-m3 embed via Ollama |
| Vector similarity | 1-2ms | pgvector HNSW or brute-force cosine |
| Rerank | <1ms | Arithmetic on <20 candidates |
| **Total** | **~900-1300ms** | Dominated by LLM; without LLM: <10ms |

---

## Fallback Hierarchy

| # | Condition | Fallback | Confidence Impact |
|---|---|---|---|
| 1 | Exact label-set miss | Best subset match: drop emotions first (all k-1 emotion subsets), then facts. Pool all matches at largest subset size (cap N=50) | −0.1 per dropped label |
| 2 | Empty pool — descend | Walk DOWN tree (BFS): collect sentences from nearest descendants with non-empty pools | −0.05 per level |
| 3 | Bitmask partial match | Soft scoring: `bitmask_score = matched_bits / required_bits`; partial matches rank lower but are not excluded | −(1.0 − bitmask_score) × 0.1 |
| 4 | LLM embedding fails | Rank by `win_rate` + `sas` only (no `vec_score`) | −0.1 |
| 5 | All fallbacks exhausted | Return null (no recommendation) | 0.0 |

**Confidence formula**: `1.0 − (dropped_labels × 0.1) − (descend_levels × 0.05) − ((1.0 − bitmask_score) × 0.1) − (embed_fail × 0.1)`, minimum 0.0

---

## PostgreSQL Schema (Complete)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE nodes (
  id              SERIAL PRIMARY KEY,
  state_id        TEXT NOT NULL,
  path_signature  TEXT NOT NULL UNIQUE,
  branch_key      JSONB,
  parent_id       INTEGER REFERENCES nodes(id),
  depth           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_nodes_path_sig ON nodes(path_signature);
CREATE INDEX idx_nodes_parent ON nodes(parent_id);

CREATE TABLE sentences (
  id                  SERIAL PRIMARY KEY,
  script_id           TEXT NOT NULL UNIQUE,
  node_id             INTEGER NOT NULL REFERENCES nodes(id),
  script_text         TEXT NOT NULL,
  bg_bitmask_int      INTEGER NOT NULL DEFAULT 0,
  win_rate            REAL NOT NULL DEFAULT 0,
  sas                 REAL NOT NULL DEFAULT 0,
  bg_background       JSONB,
  conversation_context TEXT,
  embedding           vector(1024),
  script_tsv          tsvector GENERATED ALWAYS AS (to_tsvector('simple', script_text)) STORED
);
CREATE INDEX idx_sentences_node_id ON sentences(node_id);
CREATE INDEX idx_sentences_bg_bitmask ON sentences(bg_bitmask_int);
CREATE INDEX idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_sentences_tsv ON sentences USING gin (script_tsv);
CREATE INDEX idx_sentences_script_text_trgm ON sentences USING gin (script_text gin_trgm_ops);

CREATE TABLE taxonomy_keywords (
  id          SERIAL PRIMARY KEY,
  group_name  TEXT NOT NULL,
  category    TEXT NOT NULL,
  keyword     TEXT NOT NULL,
  frequency   INTEGER NOT NULL DEFAULT 0,
  tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', keyword)) STORED
);
CREATE INDEX idx_taxonomy_tsv ON taxonomy_keywords USING gin (tsv);
CREATE INDEX idx_taxonomy_group ON taxonomy_keywords(group_name, category);
```

---

## Hybrid Search SQL (single query)

```sql
WITH candidates AS (
  SELECT script_id, script_text, win_rate, sas, bg_bitmask_int, bg_background,
         1 - (embedding <=> $query_vec) AS vec_score
  FROM sentences
  WHERE node_id = ANY($node_ids)
    AND (bg_bitmask_int & $query_bitmask) = bg_bitmask_int
)
SELECT script_id, script_text, win_rate, sas, vec_score, bg_background,
       (0.40 * win_rate + 0.30 * vec_score + 0.15 * sas) AS final_score
FROM candidates
ORDER BY final_score DESC
LIMIT 1;
```

Note: `bg_boost` is computed in Python after fetching, since it requires comparing the query's `context` dict against each candidate's `bg_background` JSONB. If `bg_boost` is negligible, the pure-SQL query above is sufficient.

---

## Scaling Path

Migration path from 31 → 100,000+ records. Retrieval is O(1) hash lookup
regardless of tree size; scaling challenges are storage, build-time, and index
maintenance — not retrieval latency.

| Dimension | Current (31 records) | Target (50K+ records) | Solution |
|-----------|---------------------|----------------------|----------|
| Nodes | 315 | 100,000+ | Tree grows with record diversity, not linearly with records |
| Node storage | JSON file | PG `nodes` table with `path_signature` B-tree index | O(log N) lookup |
| Sentence storage | JSON in-memory pools | PG `sentences` table with `node_id` index | Filter + rank in SQL |
| Vector search | char-ngram TF-IDF | pgvector HNSW index | O(log N) approximate KNN |
| Full-text search | None | PG tsvector + GIN index | BM25-ish keyword search |
| Build time | ~30s (with LLM merge) | Batch LLM + incremental rebuild | Only rebuild affected subtrees on new data |
| Child lookup | Linear scan of `children[]` | Hash map `branch_key → child` per node | O(1) child resolution |
| Context filter | Python loop | PG bitwise scoring: `popcount(bg_bitmask_int & ?) / popcount(bg_bitmask_int)` | Index + SQL scoring |
| Retrieval | JSON load + tree walk | Hash lookup + PG SELECT + pgvector | O(1) + O(pool_size) |

**Migration steps**: (1) JSON → PostgreSQL with `path_signature` column;
(2) hash index for child lookup; (3) incremental rebuild of affected subtrees;
(4) batch LLM merge with merge cache; (5) pgvector HNSW tuning
(`ef_construction`, `m`).

**Managed hosting**: Supabase (PostgreSQL + pgvector + realtime), Neon
(serverless Postgres with branching), or self-hosted
`docker run postgres:16-pgvector`.

---

## ADR Index

Authoritative decision records. Each is one line here; see
`docs/decisions/ADR-0xx-*.md` for full rationale.

| ADR | Title | Decision |
|-----|-------|----------|
| [ADR-001](docs/decisions/ADR-001-data-driven-keyword-discovery.md) | Data-driven keyword discovery | Discover state keywords from data, not prescribe — Chinese debt-collection patterns differ from English assumptions. |
| [ADR-002](docs/decisions/ADR-002-keyword-grouping.md) | Keyword grouping | Group same-meaning keyword variants under canonical names to prevent pool fragmentation. |
| [ADR-003](docs/decisions/ADR-003-suggested-domain-keywords.md) | Suggested domain keywords | Include domain-common keywords not in 31 records (`source: "suggested"`, freq 0) for forward-compatibility. |
| [ADR-004](docs/decisions/ADR-004-collector-action-discovery.md) | Collector action discovery | Discover collector action types from data too — fixed 7-type enum didn't match observed behavior. |
| [ADR-005](docs/decisions/ADR-005-data-driven-willingness-levels.md) | Data-driven willingness levels | Willingness level count determined by natural clustering (yielded 5 levels), not preset. |
| [ADR-006](docs/decisions/ADR-006-context-constraint-mapping.md) | Context constraint mapping | Map 27 raw Chinese `customer_info` fields → 21 typed English `context` fields. Expanded 9→21 on 2026-06-22. |
| [ADR-007](docs/decisions/ADR-007-carry-state-labels.md) | Carry state labels | F001 carries F000 state labels into `turns_annotated` — aligned schema is a superset, not lossy. |
| [ADR-008](docs/decisions/ADR-008-output-format-py-file.md) | Output format .py file | Output `.py` with `results = [...]` for `importlib` loading consistency; JSON would break downstream. |
| [ADR-009](docs/decisions/ADR-009-eliminate-f002-llm-state-extraction.md) | Eliminate F002 | Remove offline LLM state extraction — F000's 493/805 manual annotations suffice; online extraction is the only hot-path LLM call. |
| [ADR-010](docs/decisions/ADR-010-reward-labeling-approach.md) | Reward labeling approach | LLM + counterfactual verification + cross-validation against `plan_evaluation` for scalable, auditable R labels. |
| [ADR-011](docs/decisions/ADR-011-decision-tree-approach.md) | Decision tree approach | Nodes = collector action points, branches = customer (facts, emotions), willingness = sentence label. Consolidated start/end nodes. |
| [ADR-012](docs/decisions/ADR-012-collector-action-field.md) | collector_action field | `collector_action` on sentence entries for UI display + O(1) action filtering without parent traversal. |
| [ADR-013](docs/decisions/ADR-013-dialog-tracer.md) | Dialog tracer | Animated walkthrough (1400ms/step) validating real conversations map to tree paths. |
| [ADR-014](docs/decisions/ADR-014-bundled-js-libs.md) | Bundled JS libs | Bundle cytoscape/dagre locally (~1.5MB) for offline operation — bank internal deployments require offline. |
| [ADR-015](docs/decisions/ADR-015-local-tree-building.md) | Local tree building | Match only against `current_node` children, not globally — global reuse broke path continuity. |
| [ADR-016](docs/decisions/ADR-016-fact-by-fact-walking.md) | Fact-by-fact walking | Walk each fact/emotion one at a time, creating single-key nodes; eliminates composite-node bugs. |
| [ADR-017](docs/decisions/ADR-017-action-node-splitting.md) | Action node splitting | Force-split pools into `a:xxx` children for fact/emotion parents; uniform `fact→emotion→action→sentences`. |
| [ADR-018](docs/decisions/ADR-018-redundant-fact-collapse.md) | Redundant fact collapse | **Superseded by ADR-022.** Remove `f:X → f:X` redundant nodes; propagate `inherited_facts`. |
| [ADR-019](docs/decisions/ADR-019-state-none-handling.md) | state=None handling | Capture 58 no-action collector turns in parent pool without synthetic `other` label. |
| [ADR-020](docs/decisions/ADR-020-f005-bitmask-scoring-design.md) | F005 bitmask + scoring | 10-bit bitmask for soft scoring (matched_bits/required_bits); intersection merge; Laplace-smoothed HWR; char-bigram TF-IDF SAS (numpy only). Expanded 5→10 bits on 2026-06-22. Soft scoring replaced hard filter on 2026-06-29. |
| [ADR-021](docs/decisions/ADR-021-node-identity-dedup.md) | Node identity dedup | Identity = `(inherited_facts, inherited_emotions, branch_key)`; DAG with cycle protection. |
| [ADR-022](docs/decisions/ADR-022-redundant-emotion-collapse.md) | Redundant emotion collapse | Extend ADR-018 to collapse `anger → anger` nested emotion paths; symmetric with fact collapse. |
| [ADR-023](docs/decisions/ADR-023-sentence-pool-dedup.md) | Sentence pool dedup | `_dedup_pool` by `script_text` after every `.extend()` in 3 transforms; fixes data for all consumers. |
| [ADR-024](docs/decisions/ADR-024-embedding-architecture.md) | Embedding architecture | bge-m3 via Ollama (1024-dim, OpenAI-compatible) replaces char-ngram TF-IDF; local/no-cost/offline; unified ranking replaces dual-strategy. |
| [ADR-025](docs/decisions/ADR-025-f010-ui-architecture.md) | F010 UI architecture | Vanilla JS + FastAPI StaticFiles; no build step; CodeMirror 6 + Tailwind via CDN; same server/port; `/recommend/debug` endpoint. |
| [ADR-026](docs/decisions/ADR-026-open-set-extraction-relabel.md) | Open-set extraction + sync relabel | Open-set extraction for facts/emotions (free-form labels), closed-set for willingness; synchronous relabel pipeline normalizes through `*_descriptions` → `*_relabeled` → `llm_relabel`; self-extending taxonomy. |
