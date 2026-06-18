---
id: ADR-020
title: "F005 context tagging: bitmask encoding, HWR, SAS design"
doc_kind: decision
feature_ids: [F005]
topics: [bitmask, scoring, context-filtering, embeddings]
status: accepted
created: 2026-06-18
updated: 2026-06-18
schema_version: 1
---

# F005 Context Tagging & Quality Scoring Design

## What

Three design choices for F005:

1. **5-bit bitmask from 9 context fields**: Encode boolean-derivable fields (has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good) as bitmask for O(1) filtering. Numeric/list fields remain in bg_constraints dict.

2. **Intersection merge for multi-source sentences**: Sentences with multiple source_call_ids use bitwise AND of all source constraints. Conservative: only universally-present constraints are set.

3. **HWR (Laplace-smoothed) + SAS (TF-IDF cosine similarity)**: Two quality scores per sentence. UC and CSI deferred. SAS uses local character bigram TF-IDF + cosine similarity (no external API).

## Why

- Bitmask enables O(1) AND filtering at retrieval time vs O(n) dict comparison
- Intersection merge is the correct conservative semantics: a sentence's bitmask represents constraints present in ALL its source conversations, avoiding false specificity
- Laplace smoothing `(wins+1)/(total+2)` handles sparse data (6 R=1 / 25 R=0) without 0/0
- SAS uses character bigram TF-IDF + cosine similarity (numpy only), no external API dependency. DeepSeek does not offer an embedding endpoint; local TF-IDF is deterministic and sufficient for intra-node script similarity.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Union merge for multi-source | Too permissive — sentence used in both mortgage and non-mortgage contexts would require mortgage, excluding valid non-mortgage queries |
| Per-source bitmask list | Breaks O(1) single-integer filtering; requires list iteration |
| No smoothing (raw wins/total) | 0/0 for unused sentences; 1/1=1.0 for single R=1 is overconfident |
| DeepSeek embeddings for SAS | DeepSeek API has no embedding endpoint (only chat models deepseek-v4-flash/pro) |
| TF-IDF instead of embeddings | Adopted — character bigram TF-IDF is deterministic, no API dependency, sufficient for intra-node similarity |
| Compute UC/CSI now | Requires causal analysis and data not available at 31-record scale |
