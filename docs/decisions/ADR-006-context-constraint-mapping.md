---
id: ADR-006
title: "F001 context constraint mapping: 9 fields from customer_info"
doc_kind: decision
feature_ids: [F001]
topics: [schema, context, alignment]
status: accepted
created: 2026-06-10
updated: 2026-06-10
schema_version: 1
---

# F001 Context Constraint Mapping: 9 Fields from customer_info

## What

Map `customer_info` dict (27 Chinese-named fields) to a fixed 9-field `context` constraint dict with SOP-aligned English keys and typed values.

| SOP Field | Source | Transform |
|-----------|--------|-----------|
| `has_auto_loan` | 他行/我行是否有车贷 | Bool: contains "有车贷" |
| `has_mortgage` | 他行/我行是否有房贷 | Bool: contains "有房贷" |
| `credit_rating` | 24期缴款评等 | Enum: first char (Z=good, B/2/3=moderate, 0=bad) |
| `days_delinquent` | mob_typ | Int: M1→30, M2→60, ... |
| `total_debt` | 总欠款 | Int (strip non-digits) |
| `external_debt` | 外部欠款金额 | Int (parse "总余额NNN") |
| `has_negotiation_history` | 历史协商情况 | Bool: ≠ "无协商历史" |
| `available_plans` | 当前可使用的协商方案 | List: reduction/mina/installment |
| `social_insurance_stable` | 社保缴纳情况 | Bool: has "有社保" and not "灵活就业" |

## Why

Downstream features (F005 context tagging, F006 retrieval) need O(1) bitmask filtering on customer profile constraints. Raw `customer_info` has 27 Chinese-named string fields — unusable for programmatic filtering. The 9-field mapping provides the minimal constraint space C defined in the SOP.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep all 27 fields | Most are unused by downstream features; increases bitmask size unnecessarily |
| LLM-based extraction | Deterministic parsing is sufficient; no ambiguity in these fields |
| Normalize to enums only | Some fields (total_debt, external_debt) need numeric values for ranking, not just categories |
