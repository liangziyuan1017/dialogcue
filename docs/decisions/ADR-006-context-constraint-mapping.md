---
id: ADR-006
title: "F001 context constraint mapping: 21 fields from customer_info"
doc_kind: decision
feature_ids: [F001, F005]
topics: [schema, context, alignment]
status: accepted
created: 2026-06-10
updated: 2026-06-22
schema_version: 2
---

# F001 Context Constraint Mapping: 21 Fields from customer_info

## What

Map `customer_info` dict (27 Chinese-named fields) to a fixed 21-field `context` constraint dict with SOP-aligned English keys and typed values.

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
| `card_restricted` | 是否管制 | Bool: ≠ "可正常使用卡片" |
| `is_cash_out_customer` | 是否为套现客户 | Bool: ≠ "非套现客户" |
| `external_debt_institutions` | 外部共债机构数 | Int (parse "共N家") |
| `interest_ratio` | 利息占欠款比例 | Float (parse "N%" → N/100) |
| `installment_ratio` | 分期金额占欠款比例 | Float (parse "N%" → N/100) |
| `age` | 年龄 | Int (strip non-digits) |
| `gender` | 性别 | Str (pass-through) |
| `education` | 学历 | Enum: 未填→unknown, 高中→high_school, 大专→college, 本科→bachelor, 硕士→master, 博士→phd, else→other |
| `industry` | 行业 | Str (pass-through) |
| `has_complaint_history` | 历史投诉情况 | Bool: "没有" not in text |
| `has_legal_tools` | 当前可使用的法务工具 | Bool: ≠ "无可用的法务工具" |
| `is_negotiation_brain_customer` | 是否谈判大脑客户 | Bool: == "Y" |

## Why

Downstream features (F005 context tagging, F006 retrieval) need O(1) bitmask filtering on customer profile constraints. Raw `customer_info` has 27 Chinese-named string fields — unusable for programmatic filtering. The 21-field mapping provides the constraint space C defined in the SOP, covering both boolean-derivable fields (for bitmask) and numeric/categorical fields (for range/list filtering).

### 2026-06-22 Expansion: 9 → 21 fields

The original 9 fields covered only basic financial constraints. The expansion adds:

- **5 new boolean fields** (card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer) — these directly affect which negotiation scripts are appropriate and are now bitmask-encoded (bits 5–9)
- **3 new numeric fields** (external_debt_institutions, interest_ratio, installment_ratio) — available for range filtering in F006 retrieval
- **4 new categorical fields** (age, gender, education, industry) — available for profile-based script selection in F006

Fields excluded from mapping: 统计日期, 客户号, 申请卡片时间 (identifiers/dates), 近一个月callid, 是否完成总结 (operational metadata), 持卡客户是否疑似代理中介投诉 (sparse/unreliable).

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep all 27 fields | Some are identifiers/dates/metadata with no retrieval value; 持卡客户是否疑似代理中介投诉 is sparse and unreliable |
| LLM-based extraction | Deterministic parsing is sufficient; no ambiguity in these fields |
| Normalize to enums only | Some fields (total_debt, external_debt, interest_ratio, installment_ratio, age) need numeric values for ranking, not just categories |
| Skip age/gender/education/industry | These affect script tone and approach; even if sparse, they provide value when present |
