---
id: ADR-006
title: "F001 context constraint mapping: 18 fields from custInfo"
doc_kind: decision
feature_ids: [F001, F005]
topics: [schema, context, alignment]
status: accepted
created: 2026-06-10
updated: 2026-07-09
schema_version: 3
---

# F001 Context Constraint Mapping: 18 Fields from custInfo

## What

Map `custInfo` JSON array (tagName/tagValue pairs from the external system) to a fixed 18-field `context` constraint dict with SOP-aligned English keys and typed values.

### Boolean fields (7)

| Context Field | Source TagName | Transform |
|---------------|---------------|-----------|
| `has_business_loan` | 经营贷款余额 | Bool: float > 0 |
| `has_mortgage` | 商业房贷余额 | Bool: float > 0 |
| `has_other_loan` | 其他贷款余额 | Bool: float > 0 |
| `has_social_insurance` | 持卡人当前是否缴纳社保 | Bool: value == "是" |
| `is_high_risk_proxy_complaint` | 持卡用户是否疑似高风险代理投诉 | Bool: value == "是" |
| `is_proxy_intermediary_complaint` | 持卡用户是否疑似代理中介投诉 | Bool: value == "是" |
| `recent_repayment` | （掌生APP操作）近7天-还款操作 | Bool: value == "Y" |

### Integer fields (10)

| Context Field | Source TagName | Transform |
|---------------|---------------|-----------|
| `business_loan_balance` | 经营贷款余额 | Int: float × 10 (cents) |
| `mortgage_balance` | 商业房贷余额 | Int: float × 10 (cents) |
| `other_loan_balance` | 其他贷款余额 | Int: float × 10 (cents) |
| `wealth_value` | 理财时点值 | Int: float × 10 (cents) |
| `current_balance` | 目前余额 | Int: float × 10 (cents) |
| `days_delinquent` | mob_typ | Int: M1→30, M2→60, ... |
| `recent_contact_count` | 近7日接通次数 | Int (parse) |
| `risk_level` | 客户风险标识等级 | Int: strip "级", parse digit |
| `complaint_score` | 客户投诉评分 | Int (parse) |
| `vehicle_count` | 持卡用户名下历史车辆数 | Int (parse, default 0) |

### String fields (1)

| Context Field | Source TagName | Transform |
|---------------|---------------|-----------|
| `education` | 学历 | Enum: 未填→unknown, 高中及中专→high_school, 大专→college, 本科→bachelor, 硕士→master, 博士→phd, else→other |

## Why

Downstream features (F005 context tagging, F006 retrieval) need O(1) bitmask filtering on customer profile constraints. The raw `custInfo` JSON array uses Chinese tagName/tagValue pairs — unusable for programmatic filtering. The 18-field mapping provides the constraint space C, covering both boolean-derivable fields (for bitmask) and numeric/categorical fields (for range/list filtering).

### Migration history

- **2026-06-10**: Original 9 fields from `customer_info` dict (Chinese-named keys).
- **2026-06-22**: Expanded to 21 fields (added card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer + numeric/categorical fields).
- **2026-07-09**: Migrated to 18 fields from `custInfo` JSON array. Source changed from `customer_info` dict (Chinese keys) to `custInfo` JSON array (tagName/tagValue pairs). Fields aligned to actual data available in the external system. Removed fields not present in custInfo (has_auto_loan→has_business_loan, credit_rating→risk_level, total_debt→current_balance, external_debt, has_negotiation_history, available_plans, card_restricted, is_cash_out_customer, external_debt_institutions, interest_ratio, installment_ratio, age, gender, industry, has_complaint_history, has_legal_tools, is_negotiation_brain_customer). Added fields from custInfo (has_other_loan, has_social_insurance, is_high_risk_proxy_complaint, is_proxy_intermediary_complaint, recent_repayment, business_loan_balance, mortgage_balance, other_loan_balance, wealth_value, current_balance, recent_contact_count, risk_level, complaint_score, vehicle_count, education).

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep `customer_info` dict format | Data source changed to `custInfo` JSON array; old dict no longer populated |
| Keep all 27 original fields | Many fields not present in custInfo; stale mappings would produce all-False/0 defaults |
| LLM-based extraction | Deterministic parsing is sufficient; no ambiguity in tagName/tagValue pairs |
| Normalize to enums only | Balance and count fields need numeric values for ranking, not just categories |
