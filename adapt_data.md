# Plan: Schema Migration for `new_data.jsonl` → Pipeline Compatibility

## Problem Summary

`new_data.jsonl` has a **completely different `customer_info` schema** and **empty `plan_evaluation`** compared to `matched_data.jsonl`. The pipeline's `build_context()` in `align_schema.py` reads 21 Chinese fields from `customer_info` — 17 of them **do not exist** in `new_data.jsonl`, causing all derived `context` values to default to empty/zero/false. Meanwhile, 11 new fields in `new_data.jsonl` are **not consumed** by any code.

## Diff Summary

| Aspect | `matched_data.jsonl` (old) | `new_data.jsonl` (new) |
|--------|---------------------------|----------------------|
| Records | 35 | 10 |
| `call_date` | 202605xx (May) | 20260608 (June) |
| `cust_no` prefix | `010...` | `013/016/017/018/020/021...` |
| `plan_evaluation` | Populated markdown table | Empty string `""` |
| `customer_info` fields | 27 fields (old schema) | 14 fields (new schema) |

**Fields in BOTH (4):** `学历`, `社保缴纳情况`, `总欠款`, `持卡客户是否疑似代理中介投诉`

**Fields ONLY in old (23):** `统计日期`, `客户号`, `年龄`, `性别`, `申请卡片时间`, `行业`, `他行是否有房贷`, `他行是否有车贷`, `我行是否有房贷`, `我行是否有车贷`, `是否为套现客户`, `利息占欠款比例`, `分期金额占欠款比例`, `是否管制`, `24期缴款评等`, `外部欠款金额`, `外部共债机构数`, `历史协商情况`, `历史投诉情况`, `当前可使用的协商方案`, `当前可使用的法务工具`, `近一个月callid`, `是否完成总结`, `是否谈判大脑客户`

**Fields ONLY in new (10):** `经营贷款余额`, `商业房贷余额`, `其他贷款余额`, `理财时点值`, `ct标签`, `近7天还款操作`, `名下历史车辆数`, `近7日接通次数`, `客户风险标识等级`, `客户投诉评分`, `持卡客户是否疑似高风险代理投诉`

---

## Required Code Modifications

### 1. `src/f001_schema_alignment/align_schema.py` — `build_context()` (lines 76-102)

**Add new context fields** from `new_data.jsonl` and **make old field lookups resilient** (graceful fallback when field missing):

```python
def build_context(customer_info, mob_typ):
    return {
        # --- OLD fields (fallback to default when absent in new_data) ---
        "has_auto_loan": _parse_bool_has(customer_info.get("他行是否有车贷", ""), "有车贷")
        or _parse_bool_has(customer_info.get("我行是否有车贷", ""), "有车贷"),
        "has_mortgage": (
            _parse_bool_has(customer_info.get("他行是否有房贷", ""), "有房贷")
            or _parse_bool_has(customer_info.get("我行是否有房贷", ""), "有房贷")
            or _parse_float(customer_info.get("商业房贷余额", "0.0")) > 0
        ),
        "credit_rating": (
            _map_credit_rating(customer_info.get("24期缴款评等", ""))
            if customer_info.get("24期缴款评等", "")
            else _map_risk_level_to_credit(customer_info.get("客户风险标识等级", ""))
        ),
        "days_delinquent": _map_days_delinquent(mob_typ),
        "total_debt": _parse_int(customer_info.get("总欠款", "0")),
        "external_debt": _parse_external_debt(customer_info.get("外部欠款金额", "")),
        "has_negotiation_history": customer_info.get("历史协商情况", "") != "无协商历史",
        "available_plans": _parse_available_plans(customer_info.get("当前可使用的协商方案", "")),
        "social_insurance_stable": "有社保" in customer_info.get("社保缴纳情况", "")
        and "灵活就业" not in customer_info.get("社保缴纳情况", ""),
        "card_restricted": customer_info.get("是否管制", "") != "可正常使用卡片",
        "is_cash_out_customer": customer_info.get("是否为套现客户", "") != "非套现客户",
        "external_debt_institutions": _parse_external_debt_institutions(customer_info.get("外部共债机构数", "")),
        "interest_ratio": _parse_percentage(customer_info.get("利息占欠款比例", "0%")),
        "installment_ratio": _parse_percentage(customer_info.get("分期金额占欠款比例", "0%")),
        "age": _parse_int(customer_info.get("年龄", "0")),
        "gender": customer_info.get("性别", ""),
        "education": _map_education(customer_info.get("学历", "")),
        "industry": customer_info.get("行业", ""),
        "has_complaint_history": "没有" not in customer_info.get("历史投诉情况", "没有"),
        "has_legal_tools": customer_info.get("当前可使用的法务工具", "") != "无可用的法务工具",
        "is_negotiation_brain_customer": customer_info.get("是否谈判大脑客户", "") == "Y",
        # --- NEW fields (from new_data.jsonl) ---
        "business_mortgage_balance": _parse_float(customer_info.get("商业房贷余额", "0.0")),
        "business_loan_balance": _parse_float(customer_info.get("经营贷款余额", "0.0")),
        "other_loan_balance": _parse_float(customer_info.get("其他贷款余额", "0.0")),
        "wealth_value": _parse_float(customer_info.get("理财时点值", "0.0")),
        "ct_tags": customer_info.get("ct标签", ""),
        "recent_7d_repayment": customer_info.get("近7天还款操作", "") == "Y",
        "vehicle_count": _parse_int(customer_info.get("名下历史车辆数", "0")),
        "recent_7d_contact_count": _parse_int(customer_info.get("近7日接通次数", "0")),
        "risk_level": _map_risk_level(customer_info.get("客户风险标识等级", "")),
        "complaint_score": _parse_int(customer_info.get("客户投诉评分", "0")),
        "is_high_risk_proxy_complaint": customer_info.get("持卡客户是否疑似高风险代理投诉", "") != "否",
    }
```

**Add three new helper functions** (before `build_context`):

```python
def _parse_float(text):
    try:
        return float(str(text).strip())
    except (ValueError, TypeError):
        return 0.0

def _map_risk_level(text):
    mapping = {"1级": "low", "2级": "moderate", "3级": "high", "4级": "very_high"}
    return mapping.get(str(text).strip(), "unknown")

def _map_risk_level_to_credit(text):
    mapping = {"1级": "good", "2级": "moderate", "3级": "bad", "4级": "bad"}
    return mapping.get(str(text).strip(), "unknown")
```

---

### 2. `src/f005_context_scoring/scoring_metrics.py` — `BITMASK_FIELDS` (lines 4-15) and `BG_BACKGROUND_FIELDS` (lines 18-31)

**Add new bitmask fields** for boolean-valued new context fields:

```python
BITMASK_FIELDS = [
    "has_auto_loan",
    "has_mortgage",
    "has_negotiation_history",
    "social_insurance_stable",
    "credit_rating_good",
    "card_restricted",
    "is_cash_out_customer",
    "has_complaint_history",
    "has_legal_tools",
    "is_negotiation_brain_customer",
    "recent_7d_repayment",          # NEW
    "is_high_risk_proxy_complaint", # NEW
]
```

**Add new background fields** for string/numeric new context fields:

```python
BG_BACKGROUND_FIELDS = [
    ("age", "年龄"),
    ("gender", "性别"),
    ("education", "学历"),
    ("industry", "行业"),
    ("is_cash_out", "是否为套现客户"),
    ("is_restricted", "是否管制"),
    ("complaint_history", "历史投诉情况"),
    ("external_debt_institutions", "外部共债机构数"),
    ("interest_ratio", "利息占欠款比例"),
    ("installment_ratio", "分期金额占欠款比例"),
    ("legal_tools", "当前可使用的法务工具"),
    ("negotiation_brain", "是否谈判大脑客户"),
    # NEW fields
    ("risk_level", "客户风险标识等级"),
    ("complaint_score", "客户投诉评分"),
    ("ct_tags", "ct标签"),
    ("recent_7d_contact_count", "近7日接通次数"),
]
```

**Update `_extract_bg_constraints()`** (lines 34-46) to include new boolean fields:

```python
def _extract_bg_constraints(context):
    return {
        "has_auto_loan": bool(context.get("has_auto_loan", False)),
        "has_mortgage": bool(context.get("has_mortgage", False)),
        "has_negotiation_history": bool(context.get("has_negotiation_history", False)),
        "social_insurance_stable": bool(context.get("social_insurance_stable", False)),
        "credit_rating_good": context.get("credit_rating") in ("good", "low"),
        "card_restricted": bool(context.get("card_restricted", False)),
        "is_cash_out_customer": bool(context.get("is_cash_out_customer", False)),
        "has_complaint_history": bool(context.get("has_complaint_history", False)),
        "has_legal_tools": bool(context.get("has_legal_tools", False)),
        "is_negotiation_brain_customer": bool(context.get("is_negotiation_brain_customer", False)),
        "recent_7d_repayment": bool(context.get("recent_7d_repayment", False)),
        "is_high_risk_proxy_complaint": bool(context.get("is_high_risk_proxy_complaint", False)),
    }
```

---

### 3. `src/f006_retrieval_engine/retrieval_ranking.py` — `compute_bg_boost()` (lines 33-52)

**Add boost logic for new fields** (risk level matching, recent repayment signal):

```python
def compute_bg_boost(sentence_bg, query_bg):
    boost = 0.0
    s_industry = _first_val(sentence_bg.get("industry", ""))
    q_industry = query_bg.get("industry", "")
    if s_industry and q_industry and s_industry == q_industry:
        boost += 0.05
    s_edu = _first_val(sentence_bg.get("education", ""))
    q_edu = query_bg.get("education", "")
    if s_edu and q_edu and s_edu == q_edu:
        boost += 0.02
    q_debt = _safe_int(query_bg.get("total_debt", 0))
    s_interest = _safe_int(sentence_bg.get("interest_ratio", 0))
    s_installment = _safe_int(sentence_bg.get("installment_ratio", 0))
    if q_debt > 0 and (s_interest > 0 or s_installment > 0):
        boost += 0.03
    s_age = _safe_int(sentence_bg.get("age", 0))
    q_age = _safe_int(query_bg.get("age", 0))
    if s_age > 0 and q_age > 0 and abs(s_age - q_age) <= 10:
        boost += 0.02
    # NEW: risk level match
    s_risk = _first_val(sentence_bg.get("risk_level", ""))
    q_risk = query_bg.get("risk_level", "")
    if s_risk and q_risk and s_risk == q_risk:
        boost += 0.03
    # NEW: recent repayment signal
    if query_bg.get("recent_7d_repayment", False):
        boost += 0.02
    return boost
```

---

### 4. `src/f003_reward_labeling/reward_label.py` — `cross_validate()` (lines 167-177)

**Handle empty `plan_evaluation`** — when `plan_evaluation` is `""` (new data), skip the cross-validation warning:

```python
def cross_validate(rewarded_records):
    warnings = []
    provides_pattern = re.compile(r"(?<!未)提供|运用")
    for rec in rewarded_records:
        if rec["reward"] == 1:
            plan_eval = rec.get("plan_evaluation", "")
            if plan_eval and not provides_pattern.search(plan_eval):
                warnings.append(
                    f"{rec['call_id']}: R=1 but plan_evaluation shows no plan provided — possible mismatch"
                )
    return warnings
```

---

### 5. `src/tests/f001_schema_alignment/test_align_schema_context.py` — Update tests

**Update `test_all_9_context_fields_populated`** (line 10) — add the 11 new context keys to the expected set:

```python
context_keys = {
    "has_auto_loan", "has_mortgage", "credit_rating", "days_delinquent",
    "total_debt", "external_debt", "has_negotiation_history", "available_plans",
    "social_insurance_stable", "card_restricted", "is_cash_out_customer",
    "external_debt_institutions", "interest_ratio", "installment_ratio",
    "age", "gender", "education", "industry", "has_complaint_history",
    "has_legal_tools", "is_negotiation_brain_customer",
    # NEW fields
    "business_mortgage_balance", "business_loan_balance", "other_loan_balance",
    "wealth_value", "ct_tags", "recent_7d_repayment", "vehicle_count",
    "recent_7d_contact_count", "risk_level", "complaint_score",
    "is_high_risk_proxy_complaint",
}
```

**Add new test functions** for the new fields:

```python
def test_context_business_mortgage_balance():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["business_mortgage_balance"], float)
        assert ctx["business_mortgage_balance"] >= 0

def test_context_risk_level():
    for raw, ctx in _ctx_pairs():
        assert ctx["risk_level"] in ("low", "moderate", "high", "very_high", "unknown")

def test_context_complaint_score():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["complaint_score"], int)
        assert ctx["complaint_score"] >= 0

def test_context_recent_7d_repayment():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["recent_7d_repayment"], bool)

def test_context_is_high_risk_proxy_complaint():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["is_high_risk_proxy_complaint"], bool)
```

---

### 6. `src/tests/f005_context_scoring/test_score_tree.py` — Update tests

**Update `TestContextLookup.test_all_have_context_fields`** (lines 45-67) — add new context field assertions:

```python
assert "business_mortgage_balance" in ctx
assert "business_loan_balance" in ctx
assert "risk_level" in ctx
assert "complaint_score" in ctx
assert "recent_7d_repayment" in ctx
assert "is_high_risk_proxy_complaint" in ctx
```

**Update `TestCustomerInfoLookup.test_has_chinese_fields`** (lines 77-81) — add new field checks:

```python
assert "ct标签" in ci or "客户风险标识等级" in ci
```

**Update `TestBitmaskEncoding.test_extract_bg_constraints_from_context`** (lines 127-150) — add new bitmask fields to the test context dict and assertions:

```python
ctx = {
    "has_auto_loan": True,
    "has_mortgage": False,
    "credit_rating": "good",
    "has_negotiation_history": True,
    "social_insurance_stable": False,
    "card_restricted": True,
    "is_cash_out_customer": False,
    "has_complaint_history": False,
    "has_legal_tools": True,
    "is_negotiation_brain_customer": False,
    "recent_7d_repayment": True,
    "is_high_risk_proxy_complaint": False,
}
bg = _extract_bg_constraints(ctx)
assert bg["recent_7d_repayment"] is True
assert bg["is_high_risk_proxy_complaint"] is False
```

---

### 7. `data/data_cleaning/data_merge.py` — `EXTRA_FIELDS` (line 15)

**No change needed** — `customer_info` and `plan_evaluation` are already in `EXTRA_FIELDS`, so they'll be merged as-is regardless of schema.

---

### 8. `src/whole_pipeline.py` — Default input file (line 272)

**No change needed** — the `--data-file` CLI arg already allows specifying a different input file. The default remains `matched_data.jsonl`; users pass `--data-file new_data.jsonl` for the new data.

---

## Migration Strategy

The approach is **backward-compatible additive**:
- All old field lookups use `.get()` with defaults — they return defaults when the field is absent in `new_data.jsonl` (same as today)
- New fields are added to `build_context()` with `.get()` defaults — they return defaults when absent in `matched_data.jsonl`
- `BITMASK_FIELDS` grows by 2 — existing bitmask integers shift but this only affects new pipeline runs
- `BG_BACKGROUND_FIELDS` grows by 4 — existing background dicts get empty strings for old data
- Tests are updated to accept both schemas

## Files Modified (6 files)

| # | File | Change Type |
|---|------|-------------|
| 1 | `src/f001_schema_alignment/align_schema.py` | Add 3 helpers + 11 context fields + 2 fallback logics |
| 2 | `src/f005_context_scoring/scoring_metrics.py` | Add 2 bitmask fields + 4 background fields + update `_extract_bg_constraints` |
| 3 | `src/f006_retrieval_engine/retrieval_ranking.py` | Add 2 boost rules in `compute_bg_boost` |
| 4 | `src/f003_reward_labeling/reward_label.py` | Guard `plan_evaluation` empty check in `cross_validate` |
| 5 | `src/tests/f001_schema_alignment/test_align_schema_context.py` | Update expected keys + add 5 new tests |
| 6 | `src/tests/f005_context_scoring/test_score_tree.py` | Update context field assertions + bitmask test |
