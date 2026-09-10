---
REMOVED_FIELD_id: ADR-033
title: "custInfo migration: customer_info dict → custInfo JSON array"
doc_kind: decision
feature_ids: [F001, F005, F006]
topics: [schema, context, migration]
status: accepted
created: 2026-07-09
updated: 2026-07-09
schema_version: 1
---

# custInfo Migration: customer_info dict → custInfo JSON array

## What

Migrated the customer profile data source from `customer_info` (a dict of 27 Chinese-named string fields) to `custInfo` (a JSON array of `{tagName, tagValue}` pairs). This changed the context schema from 21 fields to 18 fields, the bitmask fields from the old set (has_auto_loan, has_negotiation_history, credit_rating_good, card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer) to the new set (has_business_loan, has_other_loan, recent_repayment, is_high_risk_proxy_complaint, is_proxy_intermediary_complaint, has_social_insurance, has_risk_flag, has_complaint, has_vehicle), and the bg_background source from `customer_info_lookup` to `context_lookup`.

## Why

- The external system changed its data format from `customer_info` dict to `custInfo` JSON array. The `customer_info` dict is now always empty.
- The new `custInfo` format uses standardized tagName/tagValue pairs, making field extraction more reliable.
- The new context fields are aligned to what actually exists in the data. Old fields like `has_auto_loan`, `has_negotiation_history`, `credit_rating_good` had no data source and were always False/defaults.
- Balance fields are now stored as digit counts in `bg_background` (e.g. 142870→6) instead of raw Chinese strings, enabling numeric proximity matching in F006.

## Impact

| Component | Change |
|-----------|--------|
| `align_schema.py` | `build_context()` reads `custInfo` JSON instead of `customer_info` dict |
| `scoring_metrics.py` | New BITMASK_FIELDS (10 fields), new BG_BACKGROUND_FIELDS (3-tuple with digit/int/passthrough transforms), `compute_bg_background` takes `context_lookup` |
| `score_tree.py` | Removed `build_customer_info_lookup`, removed `customer_info_lookup` parameter |
| `retrieval_ranking.py` | New `compute_bg_boost` with complaint_proximity, delinquent_proximity, recent_contact_signal, digits_proximity |
| `config.md` | New bg_boost keys replacing old industry_match, debt_interest_match, age_proximity_match |
| `tag_mapping.py` | Updated field names for new context schema |
| `input_data.jsonl` | 106 lines, 103 unique call_ids (deduplicated from 152 lines) |

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep parsing old `customer_info` dict | Dict is always empty; no data to parse |
| Maintain backward compatibility with both formats | No records use the old format; dead code |
| Keep old bitmask field names with always-False defaults | Misleading; downstream code would test against fields that can never be True |
