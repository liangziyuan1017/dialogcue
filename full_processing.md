# Full Processing Path: Debt Collection Script Recommendation System

## System Overview

A real-time recommendation engine for debt collection call scripts. Given a customer's utterance in an ongoing phone call, the system extracts the customer's emotional and factual state, navigates a pre-built decision tree to find relevant historical scripts, and recommends the single best collector response — ranked by historical effectiveness, semantic relevance, script diversity, and customer profile match.

**Database**: PostgreSQL + pgvector + pg_trgm (single database for metadata, vectors, bitmask filtering, and full-text search)

**API**: FastAPI, `POST /recommend`

---

## Phase 1: Ingest (offline, batch)

All data preparation happens offline. The output is a PostgreSQL database loaded with the decision tree, scored sentences, and pre-computed embeddings.

### Step 1.1: Raw Data

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
    {"level": 5, "definition": "同意还款", "boundary": "...", "example_turns": [...]}
  ]
}
```

**Output 2**: `/src/f001_schema_alignment/output_labeled.py` (per-turn state labels)

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

**Key**: `branch_key` is a dict with one key — either `"facts"` or `"emotions"` — containing the state group that led to this branch. `inherited_facts` accumulates facts from ancestor nodes. `inherited_emotions` accumulates emotions from ancestor nodes. The `state` label on customer turns may also include a `willingness` field (e.g. `"conditional"`, `"negotiating"`, `"strong"`) from F000's willingness levels — willingness is tracked in conversation state but is not used in the node key or tree structure.

### Step 1.6: F005 — Context Scoring + Embedding + Database Load

**Input**: `decision_tree.json` + `output_aligned.py` + `output_rewarded.py`

**Process** (per sentence in every node's `sentence_pool`):

1. **Bitmask encoding**: Extract `bg_constraints` from source conversation's `customer_info` → encode as 10-bit integer `bg_bitmask_int`
2. **HWR/win_rate**: Compute historical win rate: `(wins + 1) / (total + 2)` where wins = count of R=1 in `source_call_ids`
3. **SAS**: Compute Script Analogy Score via char bigram TF-IDF cosine similarity within pool (no external API — ADR-020)
4. **Conversation context extraction**: Extract the ~100 words preceding this script in the source conversation → `conversation_context` string
5. **Embedding**: `embed(conversation_context)` via DeepSeek embedding API → 768-dim float32 vector → `embedding` column (ADR-025)
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
  "embedding": [0.012, -0.034, 0.078, ...]
}
```

**PostgreSQL load** (new in this plan):

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
  '[0.012, -0.034, 0.078, ...]'::vector(768),
  to_tsvector('simple', '嗯嗯，嗯对。')
);
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

### API Endpoint

```
POST /recommend
```

### Input Schema

```json
{
  "customer_utterance": "我现在真的没钱还，能不能分期",
  "conversation_context": "招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还",
  "conversation_state": {
    "facts": ["financial_hardship"],
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

**Field descriptions:**
- `customer_utterance`: The customer's most recent turn text
- `conversation_context`: Aggregated text of the past ~100 words of dialog (both customer and collector turns)
- `conversation_state`: Accumulated state from prior turns in this call. Caller passes back the `conversation_state` from the previous API response. Note: F002 (LLM State Extraction) was eliminated per ADR-009 — offline labeling relies on F000's manual annotations (493/805 turns). Online extraction (Step 2.1) is the only LLM call in the hot path.
- `context`: Customer profile from `customer_info`, transformed to the `context` dict format (ADR-006: 21 fields mapped from Chinese `customer_info`)

---

### Step 2.1: State Extraction (LLM-first)

**Primary path**: DeepSeek LLM call

```
Prompt to DeepSeek:
---
You are a state extraction engine for a debt collection call system.

Given a customer's utterance, extract which of the following state groups apply.

FACTS (customer's situation):
- financial_hardship: customer has no money, economic difficulty
- request_installment: customer asks about installment plans
- multiple_debts: customer has debts across multiple institutions
- salary_delay: customer's salary hasn't been paid yet
- income_statement: customer describes their income
- ability_to_pay: customer claims they can pay
- account_frozen: customer's accounts are frozen
- prior_contact_attempt: customer was contacted before
- previous_agreement: customer had a prior agreement
- high_interest: customer complains about high interest
- bankruptcy: customer mentions bankruptcy
- illness: customer is ill
- family_illness: customer's family member is ill

EMOTIONS (customer's emotional state):
- pleading: customer is begging or pleading
- resistant: customer is refusing or resisting
- anxious: customer is worried or anxious
- angry: customer is angry or hostile
- cooperative: customer is willing to cooperate
- disappointment: customer is disappointed
- distress: customer is distressed
- frustration: customer is frustrated

COLLECTOR ACTIONS (what the collector did):
- empathy: collector showed empathy
- pressure: collector applied pressure
- information: collector provided information
- plan_proposal: collector proposed a payment plan
- greeting: collector greeted the customer
- closure: collector attempted to close

WILLINGNESS (customer's repayment intent):
- resistant: refuses to pay
- weak: acknowledges but resists
- conditional: will pay if conditions met
- negotiating: actively discussing payment
- cooperative: willing to cooperate
- strong: agrees to pay

Customer utterance: "我现在真的没钱还，能不能分期"

Return JSON: {"facts": [...], "emotions": [...], "actions": [...], "willingness": "..." or null, "confidence": 0.0-1.0}
---

DeepSeek response:
{
  "facts": ["request_installment"],
  "emotions": ["pleading"],
  "willingness": "conditional",
  "confidence": 0.9
}
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

**Latency**: ~800-1200ms (LLM) | ~5ms (keyword fallback)

---

### Step 2.2: State Accumulation

Merge new extractions into the existing conversation state.

**Rules:**
- Deduplicate: if a fact/emotion/action already exists, don't add it again
- Preserve order: first-seen items stay first
- Append new items to the end of their respective lists
- Willingness: overwrite with the latest non-null value (it's a scalar, not a list)

```
existing_state = {
  facts: ["financial_hardship"],     ← from turn 2
  emotions: [],
  actions: [],
  willingness: null
}

new_extraction = {
  facts: ["request_installment"],    ← from this turn
  emotions: ["pleading"],
  actions: [],
  willingness: "conditional"
}

merged_state = {
  facts: ["financial_hardship", "request_installment"],
  emotions: ["pleading"],
  actions: [],
  willingness: "conditional"
}
```

**Latency**: <1ms

---

### Step 2.3: Node Key Computation

Derive a deterministic lookup key from the accumulated conversation state. The key is a 3-tuple: `(inherited_facts, branch_key_values, inherited_emotions)`. All three components are needed — without `inherited_emotions`, 31 key collisions occur (e.g., `a:closure` under `['disappointment']` vs `['anger']` must not aggregate). Willingness is tracked in conversation state but **not** in the node key.

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

### Step 2.4: Node Lookup (O(1) hash, with aggregation)

```python
nodes = node_index[(("financial_hardship", "request_installment"), (), ("pleading",))]
# → [node_42, node_58]  — multiple nodes may share the same key
```

When a key matches multiple nodes, **aggregate all their sentence pools** into a single candidate pool (F006: avoids premature filtering by tree position).

**Fallback cascade** (if exact key miss):

1. **Key drop**: Drop the least-frequent keyword from `inherited_facts`, recompute key, retry. Each drop: −0.1 confidence.
2. **Descend fallback**: If matched nodes have empty pools but have children, walk DOWN the tree (BFS) to nearest descendants with non-empty pools. All siblings at the same depth are included. Each level: −0.05 confidence.
3. **Key drop after exhausted descend**: If descend finds nothing at any depth, drop another keyword and retry from key lookup.
4. **Root fallback**: If all keywords stripped, use root node (`initial_contact`). −0.2 confidence.

**Latency**: <1ms (hash lookup) | O(depth) with fallback

---

### Step 2.5: Candidate Retrieval + Bitmask Filter (PostgreSQL)

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

**Bitmask filter logic**: A sentence is compatible if all its required constraints are satisfied by the query.

```
sentence.bg_bitmask_int & query_bitmask == sentence.bg_bitmask_int
```

- Sentence with `bg_bitmask_int=0` (no constraints) → always passes
- Sentence with `bg_bitmask_int=2` (requires `has_mortgage`) → passes because query has bit 1 set
- Sentence with `bg_bitmask_int=16` (requires `credit_rating_good`) → filtered OUT because query doesn't have bit 4 set

**SQL query:**

```sql
SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
       bg_background, conversation_context, embedding
FROM sentences
WHERE node_id = ANY(ARRAY[42, 58])
  AND (bg_bitmask_int & 2) = bg_bitmask_int;
```

**Bitmask relaxation** (if no candidates pass filter): Strip lowest bit from `query_bitmask` and retry. Each relaxation costs -0.05 confidence.

**Latency**: ~2-5ms

---

### Step 2.6: Vector Semantic Match (pgvector)

**Step 2.6.1**: Embed the query conversation context

```python
query_vec = embed_single("招商银行信用卡中心来电 请问是张女士吗 是的 告知逾期金额 客户说经济困难 没钱还")
# → [0.015, -0.042, 0.091, ...]  (768-dim float32)
```

**Step 2.6.2**: Compute cosine similarity against each candidate's stored `embedding`

**Option A — Single SQL query** (combines Steps 2.5 + 2.6 + 2.7):

```sql
SELECT script_id, script_text, win_rate, sas, bg_background,
       1 - (embedding <=> $query_vec) AS vec_score
FROM sentences
WHERE node_id = ANY($node_ids)
  AND (bg_bitmask_int & $query_bitmask) = bg_bitmask_int
ORDER BY (0.40 * win_rate + 0.30 * (1 - (embedding <=> $query_vec)) + 0.15 * sas) DESC
LIMIT 1;
```

**Option B — Fetch candidates, compute in Python** (more flexible for `bg_boost`):

Fetch candidates with embeddings from PG, compute `vec_score` + `bg_boost` + `final_score` in Python.

**Latency**: ~50-100ms (DeepSeek embed API) + ~2ms (pgvector cosine)

---

### Step 2.7: Rerank (Weighted Fusion)

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

**Strategy switch** (bg_boost applicability only):

```python
RANKING_STRATEGY = "limited"  # or "full"

def recommend(inherited_facts, branch_key_values, inherited_emotions, query_bitmask, conversation_context, query_bg, strategy=RANKING_STRATEGY):
    key = (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))
    nodes = lookup_by_key(key, node_index)
    pool = aggregate_pools(nodes)
    filtered = filter_by_bitmask(pool, query_bitmask)
    # vec_score computed via pgvector or DeepSeek embed + cosine
    bg_boost = compute_bg_boost(...) if strategy == "full" else 0.0
    final_score = 0.40 * win_rate + 0.30 * vec_score + 0.15 * sas + 0.15 * bg_boost
    return top_by_final_score(filtered)
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

**Processing:**
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

## Latency Budget

| Step | Latency | Notes |
|---|---|---|
| State extraction (LLM) | 800-1200ms | Dominated by DeepSeek API call |
| State accumulation | <1ms | In-memory set operations |
| Node key computation | <1ms | Sort + tuple |
| Node lookup + aggregation | <1ms | Hash map O(1) + pool merge |
| Candidate retrieval + bitmask | 2-5ms | Indexed PG query |
| Vector embedding (query) | 50-100ms | DeepSeek embed API call |
| Vector similarity | 1-2ms | pgvector HNSW or brute-force cosine |
| Rerank | <1ms | Arithmetic on <20 candidates |
| **Total** | **~900-1300ms** | Dominated by LLM; without LLM: <10ms |

---

## Fallback Hierarchy

| # | Condition | Fallback | Confidence Impact |
|---|---|---|---|
| 1 | Exact key miss | Drop least-frequent keyword from `inherited_facts`, retry | −0.1 per drop |
| 2 | Empty pool — descend | Walk DOWN tree (BFS): collect sentences from nearest descendants with non-empty pools | −0.05 per level |
| 3 | Descend exhausted → key drop | Drop another keyword from `inherited_facts`, retry from key lookup | −0.1 per drop |
| 4 | Bitmask filter returns empty | Relax bitmask (drop lowest bit) | −0.05 per relaxation |
| 5 | LLM embedding fails | Rank by `win_rate` + `sas` only (no `vec_score`) | −0.1 |
| 6 | All fallbacks exhausted | Return null (no recommendation) | 0.0 |

**Confidence formula**: `1.0 − (key_drops × 0.1) − (descend_levels × 0.05) − (bitmask_relaxations × 0.05) − (embed_fail × 0.1)`, minimum 0.0

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
  embedding           vector(768),
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
