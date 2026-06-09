# Implementation Plan: Debt Collection Script Recommendation System

## Overview

Build a full offline prototype of the Online Real-Time Script Recommendation System defined in the SOP, using the 31 cleaned call records in `data/output_manual.py`. The prototype validates the core loop: **state extraction → reward labeling → decision tree construction → context-aware retrieval → quality metrics**, with a clear scaling path to 10,000 records.

**LLM engine:** DeepSeek (consistent with existing pipeline)
**Input data:** 31 records, 805 turns, all M1 delinquency stage
**Data already cleaned:** ASR noise removal, emotion preservation, dialogue reconstruction, and manual verification are complete

---

## Phase 0: Data Schema Alignment

Map `output_manual.py` record fields to the SOP's data model.

### Input schema (current)

```
Record: { call_id, custno, response: { dialog: [{ role, text, label?, alert? }] },
          call_date, coll_user_id, mob_typ, talk_time, plan_evaluation, customer_info }
```

### Target schema (SOP-aligned)

Create a processed output with these new structures per record:

| New Field | Source | Description |
|-----------|--------|-------------|
| `turns_annotated` | Derived | Each turn enriched with state keywords (customer turns) and action text (collector turns) |
| `reward` | Derived | R ∈ {0, 1} — did the call result in repayment commitment? |
| `state_transitions` | Derived | List of (Sᵢ → aᵢ → Sᵢ₊₁) tuples extracted from the annotated turns |
| `context` | `customer_info` | Mapped to SOP context constraint space C |

### Context constraint mapping from `customer_info`

| SOP Field | Source Field | Transform |
|-----------|-------------|-----------|
| `has_auto_loan` | `他行是否有车贷` / `我行是否有车贷` | Bool: contains "有车贷" |
| `has_mortgage` | `他行是否有房贷` / `我行是否有房贷` | Bool: contains "有房贷" |
| `credit_rating` | `24期缴款评等` | Enum: map first char (Z=good, B=moderate, 0=bad) |
| `days_delinquent` | `mob_typ` | Int: M1 → ~30 days |
| `total_debt` | `总欠款` | Int (parse numeric) |
| `external_debt` | `外部欠款金额` | Int (parse numeric) |
| `has_negotiation_history` | `历史协商情况` | Bool: ≠ "无协商历史" |
| `available_plans` | `当前可使用的协商方案` | List of plan types |
| `social_insurance_stable` | `社保缴纳情况` | Bool: contains "有社保" and not "灵活就业" |

**Deliverable:** Script `0_schema_align.py` — reads `output_manual.py`, outputs `output_aligned.py` with enriched schema.

---

## Phase 1: LLM State Extraction Pipeline

For each **customer turn**, extract the composite state keyword set:

**S = { Emotion Tag + Fact Tag + Repayment Willingness }**

### 1.1 Extraction dimensions

| Dimension | Tags | Examples |
|-----------|------|----------|
| Emotion | anger, anxiety, fatigue, calmness, defensiveness, embarrassment, pleading, resignation | 焦虑, 愤怒, 疲惫 |
| Fact | unemployment, illness, car_accident, forgot_payment, salary_delay, business_failure, family_issue, multiple_debt, card_frozen, legal_action | 失业, 生病, 工资卡冻结 |
| Willingness | strong, weak, resistant, conditional, negotiating | 强, 弱, 抗拒 |

### 1.2 LLM prompt design

- Input: the customer turn text + preceding 3 turns for context
- Output: JSON `{ "emotion": [...], "fact": [...], "willingness": "..." }`
- Model: `deepseek-chat`, temperature=0.1
- Batch: process all customer turns across 31 records
- Resume-safe: skip already-annotated turns

### 1.3 Collector action extraction

For each **collector turn**, extract:
- `action_type`: one of {greeting, information, proposal, pressure, empathy, threat, closure}
- `action_text`: the original turn text (preserved verbatim per SOP — "strictly prohibited from any modification")

**Deliverable:** Script `1_state_extract.py` — reads `output_aligned.py`, outputs `output_states.py` with all turns annotated.

---

## Phase 2: Reward Determination

Determine R ∈ {0, 1} for each conversation based on whether the customer made a repayment commitment.

### 2.1 Trigger phrase detection

LLM scans the final portion of each conversation for:

- Explicit agreement to repay ("好，我还", "我明天处理")
- Promise to handle on a specific date ("下个月15号之前", "周一之前")
- Acceptance of an installment/settlement plan ("调减方案可以", "分期我接受")
- Partial payment commitment ("先还1000", "最低还款我来处理")

### 2.2 Counterfactual verification

For R=1 cases, the LLM performs a lightweight causal check:
- Did the commitment follow a specific collector action?
- Was the commitment the customer's independent decision or clearly prompted by a collector turn?

This assigns **credit** to the preceding collector action for the positive outcome.

### 2.3 Output

Each record gets:
```json
{
  "reward": 1,
  "reward_evidence": "客户在turn 42同意调减方案，此前催收员在turn 40提出方案",
  "reward_action_credit": { "turn_index": 40, "action_text": "..." }
}
```

**Deliverable:** Script `2_reward_label.py` — reads `output_states.py`, outputs `output_rewarded.py`.

---

## Phase 3: Decision Tree Construction

Build the state-transition decision tree from the 31 annotated conversations.

### 3.1 State transition extraction

For each conversation, extract the path:

```
S₀ → a₀ → S₁ → a₁ → S₂ → ... → Sₙ
```

Where:
- Sᵢ = composite keyword set from customer turn i
- aᵢ = collector action from collector turn i

### 3.2 Path merging

When multiple conversations share similar state sequences, merge them:
- Normalize keyword sets (lexicographic sort, per SOP §4.1)
- Merge paths with identical or near-identical state sequences
- At each node, accumulate all historical collector sentences that appeared at that state

### 3.3 Tree structure

```python
{
  "root": {
    "state_id": "initial_contact",
    "keywords": [],
    "children": {
      "anxiety+unemployment+weak": {
        "state_id": "anxiety+unemployment+weak",
        "keywords": ["anxiety", "unemployment", "weak"],
        "sentence_pool": [
          {
            "script_text": "先生，我理解您现在的困难...",
            "script_id": "hash...",
            "win_rate": 0.0,
            "uplift_score": 0.0,
            "source_call_ids": ["2317941..."],
            "bg_constraints": {}
          }
        ],
        "children": { ... }
      }
    }
  }
}
```

### 3.4 Fallback strategy

Per SOP §4.1: if an exact state match is not found, progressively remove emotion tags, then fact tags, and retry matching against sub-states.

**Deliverable:** Script `3_build_tree.py` — reads `output_rewarded.py`, outputs `decision_tree.json`.

---

## Phase 4: Context Constraint Integration

Map `customer_info` fields to background constraint tags on each historical sentence in the decision tree.

### 4.1 Per-sentence background tagging

For each sentence in the tree's leaf pools, inherit the context of the source conversation's customer profile:

```json
{
  "bg_constraints": {
    "has_mortgage": true,
    "has_auto_loan": false,
    "credit_rating": "moderate",
    "days_delinquent_range": "M1",
    "total_debt_range": "60k-100k",
    "external_debt": true,
    "social_insurance_stable": false
  }
}
```

### 4.2 Hard filtering bitmask

Convert `bg_constraints` to a bitmask for O(1) filtering at retrieval time:

| Bit | Field | 0 | 1 |
|-----|-------|---|---|
| 0 | has_mortgage | no | yes |
| 1 | has_auto_loan | no | yes |
| 2 | credit_good | no | yes |
| 3 | external_debt | no | yes |
| 4 | social_insurance_stable | no | yes |

**Deliverable:** Script `4_context_tag.py` — reads `decision_tree.json` + `output_rewarded.py`, outputs `decision_tree_tagged.json`.

---

## Phase 5: Retrieval & Ranking Prototype

Build an LLM-based retrieval prototype that, given a real-time customer utterance + context, returns the top-1 recommended historical sentence.

### 5.1 Retrieval flow

```
Customer utterance (real-time)
    │
    ▼  LLM state extraction (same as Phase 1)
    │  → S = { anxiety + salary_delay + weak }
    │
    ▼  Decision tree traversal
    │  → Exact match or fallback to sub-state
    │  → Candidate sentence pool at matched node
    │
    ▼  Context hard-filtering (bitmask AND)
    │  → Eliminate sentences with incompatible bg_constraints
    │
    ▼  Ranking by HWR (primary) + UC (secondary)
    │  → Top-1 historical sentence
    │
    ▼  Output
```

### 5.2 LLM-based soft matching fallback

If the extracted state keywords don't match any tree node (even after fallback), use DeepSeek to:
1. Embed the state keywords
2. Find the semantically closest node via cosine similarity
3. Retrieve from that node's sentence pool

This implements the SOP's Solution B "vector soft matching" using DeepSeek embeddings instead of a dedicated vector DB.

### 5.3 Prototype interface

```python
def recommend(
    customer_utterance: str,
    context: dict,           # customer profile
    recent_turns: list,      # last 3 turns for context
    tree: dict,              # decision tree
) -> dict:
    """Returns { script_text, state_id, win_rate, confidence }"""
```

**Deliverable:** Script `5_retrieve.py` + `retrieval_engine.py` (library).

---

## Phase 6: Quality Metrics

Calculate backend quality metrics for every sentence in the decision tree.

### 6.1 Historical Win Rate (HWR)

For each sentence at a given state node + background combination:

```
HWR = count(R=1 after this sentence) / count(this sentence used)
```

With 31 records, many sentences will appear only once. Apply Laplace smoothing:

```
HWR_smoothed = (wins + 1) / (uses + 2)
```

### 6.2 Semantic Alignment Score (SAS)

Cosine similarity between:
- The current context vector (state keywords + background)
- The historical context vector stored with the sentence

Use DeepSeek embeddings for vectorization.

### 6.3 Uplift Contribution (UC) — deferred

Full causal uplift scoring requires A/B testing or propensity matching, which needs 10K+ records. For the prototype, set UC=0 and flag for future computation.

### 6.4 Compliance & Stability Index (CSI) — deferred

Requires multi-collector usage data. Flag for future computation.

**Deliverable:** Script `6_metrics.py` — reads `decision_tree_tagged.json`, outputs `decision_tree_scored.json` with HWR and SAS populated.

---

## Phase 7: Scaling Path to 10,000 Records

When the data volume grows from 31 → 10,000:

| Component | Current (31 records) | Scaled (10K records) |
|-----------|---------------------|---------------------|
| State extraction | DeepSeek API, sequential | DeepSeek API, batched + parallel |
| Decision tree | In-memory dict, JSON file | PostgreSQL + pgvector or graph DB (Neo4j) |
| Retrieval | Python function, exact match + LLM fallback | Solution A: BERT-ONNX + in-memory trie (<500ms) |
| | | Solution B: 7B vLLM + Milvus vector search (<2s) |
| Metrics | Laplace-smoothed HWR | Full HWR + UC (causal inference) + CSI |
| Context filtering | Dict lookup | Bitmask AND in C++ / Rust |
| Data format | `.py` files with `results = [...]` | PostgreSQL tables per SOP §2.4 DDL |

### Migration steps

1. **Schema migration:** Load `output_manual.py` format into PostgreSQL tables (`state_node_definition`, `historical_script_pool`)
2. **Model training:** Fine-tune DeBERTa-v3-small on the 10K annotated records for multi-label state classification (Solution A)
3. **Vector index:** Build Milvus/pgvector index on sentence embeddings for soft matching (Solution B)
4. **Metrics pipeline:** Batch-compute HWR/UC/CSI offline, stream-update online
5. **Latency optimization:** Export BERT to ONNX Runtime with INT8 quantization, implement C++ trie traversal

---

## Execution Order

```
output_manual.py
    │
    ▼  Phase 0: 0_schema_align.py
    └── output_aligned.py
            │
            ▼  Phase 1: 1_state_extract.py
            └── output_states.py
                    │
                    ▼  Phase 2: 2_reward_label.py
                    └── output_rewarded.py
                            │
                            ▼  Phase 3: 3_build_tree.py
                            └── decision_tree.json
                                    │
                                    ▼  Phase 4: 4_context_tag.py
                                    └── decision_tree_tagged.json
                                            │
                                            ▼  Phase 6: 6_metrics.py
                                            └── decision_tree_scored.json

Phase 5: 5_retrieve.py + retrieval_engine.py
  (consumes decision_tree_scored.json + real-time input)
```

---

## Key Design Decisions

1. **LLM-only for prototype:** All extraction, reward, and retrieval use DeepSeek API — no model training needed for 31 records. Training is deferred to the scaling phase.
2. **Verbatim sentence preservation:** Per SOP, historical collector sentences are stored and recommended exactly as spoken — no rewriting, no polishing.
3. **Resume safety:** All scripts follow the existing pipeline convention — checkpoint after each record, skip already-processed IDs.
4. **Labeled turn handling:** The 70 inferred turns (marked `"label": "1"`) are included in state extraction but flagged so they can be excluded from reward credit assignment if desired.
5. **plan_evaluation as validation:** The existing `plan_evaluation` field (调减方案/MINA方案/促成技巧) per record can be used to validate reward labels — if `plan_evaluation` shows a plan was accepted, R should be 1.
