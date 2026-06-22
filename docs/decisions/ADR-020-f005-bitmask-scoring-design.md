---
id: ADR-020
title: "F005 context tagging: bitmask encoding, HWR, SAS design"
doc_kind: decision
feature_ids: [F005]
topics: [bitmask, scoring, context-filtering, embeddings]
status: accepted
created: 2026-06-18
updated: 2026-06-22
schema_version: 2
---

# F005 Context Tagging & Quality Scoring Design

## What

Three design choices for F005:

1. **10-bit bitmask from 21 context fields**: Encode boolean-derivable fields (has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good, card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer) as bitmask for O(1) filtering. Numeric/categorical/list fields remain in bg_constraints dict and bg_background dict.

2. **Intersection merge for multi-source sentences**: Sentences with multiple source_call_ids use bitwise AND of all source constraints. Conservative: only universally-present constraints are set.

3. **HWR (Laplace-smoothed) + SAS (TF-IDF cosine similarity)**: Two quality scores per sentence. UC and CSI deferred. SAS uses local character bigram TF-IDF + cosine similarity (no external API).

## Why

- Bitmask enables O(1) AND filtering at retrieval time vs O(n) dict comparison
- Intersection merge is the correct conservative semantics: a sentence's bitmask represents constraints present in ALL its source conversations, avoiding false specificity
- Laplace smoothing `(wins+1)/(total+2)` handles sparse data (6 R=1 / 25 R=0) without 0/0
- SAS uses character bigram TF-IDF + cosine similarity (numpy only), no external API dependency. DeepSeek does not offer an embedding endpoint; local TF-IDF is deterministic and sufficient for intra-node script similarity.

### 2026-06-22 Expansion: 5-bit → 10-bit bitmask

Expanded from 5 to 10 boolean bitmask fields. New fields and rationale:

| Bit | Field | Rationale |
|-----|-------|-----------|
| 5 | `card_restricted` | Restricted cards change which negotiation scripts apply |
| 6 | `is_cash_out_customer` | Cash-out customers may need different handling |
| 7 | `has_complaint_history` | Complaint-prone customers may need softer scripts |
| 8 | `has_legal_tools` | Legal tools available changes negotiation leverage |
| 9 | `is_negotiation_brain_customer` | Pre-existing strategy customers may need different approach |

Bitmask range expanded from 0–31 to 0–1023. Compatibility check unchanged: `(sentence_bitmask & query_bitmask) == sentence_bitmask`.

bg_background dict also expanded from 7 to 12 fields to carry the new numeric/categorical data (external_debt_institutions, interest_ratio, installment_ratio, legal_tools, negotiation_brain).

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Union merge for multi-source | Too permissive — sentence used in both mortgage and non-mortgage contexts would require mortgage, excluding valid non-mortgage queries |
| Per-source bitmask list | Breaks O(1) single-integer filtering; requires list iteration |
| No smoothing (raw wins/total) | 0/0 for unused sentences; 1/1=1.0 for single R=1 is overconfident |
| DeepSeek embeddings for SAS | DeepSeek API has no embedding endpoint (only chat models deepseek-v4-flash/pro) |
| TF-IDF instead of embeddings | Adopted — character bigram TF-IDF is deterministic, no API dependency, sufficient for intra-node similarity |
| Compute UC/CSI now | Requires causal analysis and data not available at 31-record scale |
| Encode age/education as bitmask bits | Age is numeric (range filtering), education is multi-category — not suitable for binary encoding |
| Keep 5-bit bitmask | New boolean fields (card_restricted, etc.) directly affect script applicability; excluding them would produce false-positive matches |
