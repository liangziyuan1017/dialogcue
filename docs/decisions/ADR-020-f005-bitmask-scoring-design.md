---
id: ADR-020
title: "F005 context tagging: bitmask encoding, HWR, SAS, embedding design"
doc_kind: decision
feature_ids: [F005]
topics: [bitmask, scoring, context-filtering, embeddings]
status: accepted
created: 2026-06-18
updated: 2026-07-09
schema_version: 4
---

# F005 Context Tagging & Quality Scoring Design

## What

Four design choices for F005:

1. **10-bit bitmask from 18 context fields**: Encode boolean-derivable fields (has_business_loan, has_mortgage, has_other_loan, recent_repayment, is_high_risk_proxy_complaint, is_proxy_intermediary_complaint, has_social_insurance, has_risk_flag [risk_level>0], has_complaint [complaint_score>0], has_vehicle [vehicle_count>0]) as bitmask for O(1) filtering. Numeric/categorical fields remain in `bg_background` dict for `bg_boost` matching.

2. **Intersection merge for multi-source sentences**: Sentences with multiple source_call_ids use bitwise AND of all source constraints. Conservative: only universally-present constraints are set.

3. **HWR (Laplace-smoothed) + SAS (TF-IDF cosine similarity)**: Two quality scores per sentence. UC and CSI deferred. SAS uses local character bigram TF-IDF + cosine similarity (no external API) for intra-pool script diversity.

4. **BGE-M3 embedding for conversation context similarity**: Compute `embed(conversation_context)` per sentence via Ollama bge-m3 → 1024-dim float32 vector stored in `embedding` field. At retrieval time (F006), pgvector cosine similarity provides `vec_score` for cross-conversation semantic matching.

## Why

- Bitmask enables O(1) AND filtering at retrieval time vs O(n) dict comparison
- Intersection merge is the correct conservative semantics: a sentence's bitmask represents constraints present in ALL its source conversations, avoiding false specificity
- Laplace smoothing `(wins+1)/(total+2)` handles sparse data without 0/0
- SAS uses character bigram TF-IDF + cosine similarity (numpy only), no external API dependency. Sufficient for intra-node script similarity (diversity measure).
- BGE-M3 embedding provides cross-conversation semantic matching that TF-IDF char-bigram cannot achieve — it captures meaning beyond surface character overlap. pgvector HNSW index enables efficient approximate nearest neighbor search at retrieval time.

### Bitmask field history

| Date | Fields | Range | Notes |
|------|--------|-------|-------|
| 2026-06-18 | 5 fields (has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good) | 0–31 | Original design |
| 2026-06-22 | 10 fields (+ card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer) | 0–1023 | Expansion |
| 2026-07-09 | 10 fields (has_business_loan, has_mortgage, has_other_loan, recent_repayment, is_high_risk_proxy_complaint, is_proxy_intermediary_complaint, has_social_insurance, has_risk_flag, has_complaint, has_vehicle) | 0–1023 | custInfo migration — new field names aligned to actual data |

### `bg_background` design (2026-07-09)

`bg_background` is sourced from `context_lookup` (not `customer_info_lookup`). Fields use a 3-tuple format `(field_name, source_key, transform)`:

| Field | Source | Transform | Purpose |
|-------|--------|-----------|---------|
| `business_loan_digits` | context.business_loan_balance | digit count | Normalize balance magnitude for similarity |
| `mortgage_balance_digits` | context.mortgage_balance | digit count | |
| `other_loan_digits` | context.other_loan_balance | digit count | |
| `wealth_digits` | context.wealth_value | digit count | |
| `current_balance_digits` | context.current_balance | digit count | |
| `education` | context.education | passthrough | Categorical match |
| `days_delinquent` | context.days_delinquent | int | Proximity match |
| `recent_contact_count` | context.recent_contact_count | int | Signal boost |
| `risk_level` | context.risk_level | int | Exact match |
| `complaint_score` | context.complaint_score | int | Proximity match |

**Digit count transform**: `len(str(abs(value)))` for value > 0, else 0. Normalizes balance magnitude (e.g. 142870→6, 0→0) for similarity comparison without exposing raw financial figures.

**Aggregation**: For multi-source sentences, numeric fields use `max()` (most severe/recent), passthrough fields use first-common or comma-joined union.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Union merge for multi-source | Too permissive — sentence used in both mortgage and non-mortgage contexts would require mortgage, excluding valid non-mortgage queries |
| Per-source bitmask list | Breaks O(1) single-integer filtering; requires list iteration |
| No smoothing (raw wins/total) | 0/0 for unused sentences; 1/1=1.0 for single R=1 is overconfident |
| DeepSeek embeddings for SAS | SAS measures intra-pool diversity; TF-IDF char-bigram is sufficient and deterministic |
| TF-IDF for conversation context similarity | Too shallow for cross-conversation semantic matching — character overlap misses meaning |
| Compute UC/CSI now | Requires causal analysis and data not available at current scale |
| Encode numeric fields as bitmask bits | Balance/count fields are numeric (range/proximity filtering), not suitable for binary encoding |
| Source bg_background from customer_info_lookup | customer_info dict is empty after custInfo migration; all data now in context dict |
