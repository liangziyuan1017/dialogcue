from f001_schema_alignment.align_schema import align_all, build_context
from f000_keyword_discovery.load_data import load_records


def _ctx_pairs():
    records = load_records()
    return [(raw, build_context(raw["customer_info"], raw.get("mob_typ", ""))) for raw in records]


def test_all_9_context_fields_populated():
    aligned = align_all()
    context_keys = {
        "has_auto_loan", "has_mortgage", "credit_rating", "days_delinquent",
        "total_debt", "external_debt", "has_negotiation_history", "available_plans",
        "social_insurance_stable", "card_restricted", "is_cash_out_customer",
        "external_debt_institutions", "interest_ratio", "installment_ratio",
        "age", "gender", "education", "industry", "has_complaint_history",
        "has_legal_tools", "is_negotiation_brain_customer",
    }
    for rec in aligned:
        assert set(rec["context"].keys()) == context_keys
        for k in context_keys:
            assert rec["context"][k] is not None, f"{rec['call_id']}: context.{k} is None"


def test_context_no_nulls_in_required_fields():
    aligned = align_all()
    for rec in aligned:
        ctx = rec["context"]
        assert isinstance(ctx["has_auto_loan"], bool)
        assert isinstance(ctx["has_mortgage"], bool)
        assert ctx["credit_rating"] in ("good", "moderate", "bad", "unknown")
        assert isinstance(ctx["days_delinquent"], int)
        assert isinstance(ctx["total_debt"], int)
        assert isinstance(ctx["external_debt"], int)
        assert isinstance(ctx["has_negotiation_history"], bool)
        assert isinstance(ctx["available_plans"], list)
        assert isinstance(ctx["social_insurance_stable"], bool)
        assert isinstance(ctx["card_restricted"], bool)
        assert isinstance(ctx["is_cash_out_customer"], bool)
        assert isinstance(ctx["external_debt_institutions"], int)
        assert isinstance(ctx["interest_ratio"], float)
        assert isinstance(ctx["installment_ratio"], float)
        assert isinstance(ctx["age"], int)
        assert isinstance(ctx["gender"], str)
        assert isinstance(ctx["education"], str)
        assert isinstance(ctx["industry"], str)
        assert isinstance(ctx["has_complaint_history"], bool)
        assert isinstance(ctx["has_legal_tools"], bool)
        assert isinstance(ctx["is_negotiation_brain_customer"], bool)


def test_context_has_auto_loan():
    for raw, ctx in _ctx_pairs():
        ci = raw["customer_info"]
        expected = ("有车贷" in ci.get("他行是否有车贷", "")) or ("有车贷" in ci.get("我行是否有车贷", ""))
        assert ctx["has_auto_loan"] == expected


def test_context_has_mortgage():
    for raw, ctx in _ctx_pairs():
        ci = raw["customer_info"]
        expected = ("有房贷" in ci.get("他行是否有房贷", "")) or ("有房贷" in ci.get("我行是否有房贷", ""))
        assert ctx["has_mortgage"] == expected


def test_context_social_insurance_stable():
    for raw, ctx in _ctx_pairs():
        si = raw["customer_info"].get("社保缴纳情况", "")
        expected = "有社保" in si and "灵活就业" not in si
        assert ctx["social_insurance_stable"] == expected


def test_context_days_delinquent_m1():
    for raw, ctx in _ctx_pairs():
        if raw.get("mob_typ") == "M1":
            assert ctx["days_delinquent"] == 30


def test_context_negotiation_history():
    for raw, ctx in _ctx_pairs():
        expected = raw["customer_info"].get("历史协商情况", "") != "无协商历史"
        assert ctx["has_negotiation_history"] == expected


def test_context_total_debt_parsed():
    for raw, ctx in _ctx_pairs():
        assert ctx["total_debt"] > 0


def test_context_external_debt_parsed():
    for raw, ctx in _ctx_pairs():
        assert ctx["external_debt"] >= 0


def test_context_available_plans():
    for raw, ctx in _ctx_pairs():
        for plan in ctx["available_plans"]:
            assert plan in ("reduction", "mina", "installment")


def test_context_card_restricted():
    for raw, ctx in _ctx_pairs():
        expected = raw["customer_info"].get("是否管制", "") != "可正常使用卡片"
        assert ctx["card_restricted"] == expected


def test_context_is_cash_out_customer():
    for raw, ctx in _ctx_pairs():
        expected = raw["customer_info"].get("是否为套现客户", "") != "非套现客户"
        assert ctx["is_cash_out_customer"] == expected


def test_context_external_debt_institutions():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["external_debt_institutions"], int)
        assert ctx["external_debt_institutions"] >= 0


def test_context_interest_ratio():
    for raw, ctx in _ctx_pairs():
        assert 0.0 <= ctx["interest_ratio"] <= 1.0


def test_context_installment_ratio():
    for raw, ctx in _ctx_pairs():
        assert 0.0 <= ctx["installment_ratio"] <= 1.0


def test_context_age():
    for raw, ctx in _ctx_pairs():
        assert isinstance(ctx["age"], int)
        assert ctx["age"] >= 0


def test_context_education():
    for raw, ctx in _ctx_pairs():
        assert ctx["education"] in ("unknown", "high_school", "college", "bachelor", "master", "phd", "other")


def test_context_has_complaint_history():
    for raw, ctx in _ctx_pairs():
        expected = "没有" not in raw["customer_info"].get("历史投诉情况", "没有")
        assert ctx["has_complaint_history"] == expected


def test_context_has_legal_tools():
    for raw, ctx in _ctx_pairs():
        expected = raw["customer_info"].get("当前可使用的法务工具", "") != "无可用的法务工具"
        assert ctx["has_legal_tools"] == expected


def test_context_is_negotiation_brain_customer():
    for raw, ctx in _ctx_pairs():
        expected = raw["customer_info"].get("是否谈判大脑客户", "") == "Y"
        assert ctx["is_negotiation_brain_customer"] == expected
