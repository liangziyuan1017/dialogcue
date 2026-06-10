from src.align_schema import align_all, align_record, build_context, build_turns_annotated
from src.load_data import load_records


def test_all_31_records_present():
    aligned = align_all()
    assert len(aligned) == 31


def test_every_record_has_required_fields():
    aligned = align_all()
    for rec in aligned:
        assert "turns_annotated" in rec
        assert "reward" in rec
        assert "state_transitions" in rec
        assert "context" in rec


def test_reward_is_null():
    aligned = align_all()
    for rec in aligned:
        assert rec["reward"] is None


def test_state_transitions_empty():
    aligned = align_all()
    for rec in aligned:
        assert rec["state_transitions"] == []


def test_all_9_context_fields_populated():
    aligned = align_all()
    context_keys = {
        "has_auto_loan",
        "has_mortgage",
        "credit_rating",
        "days_delinquent",
        "total_debt",
        "external_debt",
        "has_negotiation_history",
        "available_plans",
        "social_insurance_stable",
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


def test_original_dialog_preserved_verbatim():
    records = load_records()
    aligned = align_all()
    for raw, aln in zip(records, aligned):
        raw_texts = [t["text"] for t in raw["response"]["dialog"]]
        aln_texts = [t["text"] for t in aln["turns_annotated"]]
        assert raw_texts == aln_texts, f"Mismatch in call_id {raw['call_id']}"


def test_turns_annotated_structure():
    aligned = align_all()
    for rec in aligned:
        for turn in rec["turns_annotated"]:
            assert "turn_index" in turn
            assert "role" in turn
            assert "text" in turn
            assert turn["role"] in ("客户", "催收员")


def test_context_has_auto_loan():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ("有车贷" in ci.get("他行是否有车贷", "")) or (
            "有车贷" in ci.get("我行是否有车贷", "")
        )
        assert ctx["has_auto_loan"] == expected


def test_context_has_mortgage():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ("有房贷" in ci.get("他行是否有房贷", "")) or (
            "有房贷" in ci.get("我行是否有房贷", "")
        )
        assert ctx["has_mortgage"] == expected


def test_context_social_insurance_stable():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        si = ci.get("社保缴纳情况", "")
        expected = "有社保" in si and "灵活就业" not in si
        assert ctx["social_insurance_stable"] == expected


def test_context_days_delinquent_m1():
    records = load_records()
    for raw in records:
        ctx = build_context(raw["customer_info"], raw.get("mob_typ", ""))
        if raw.get("mob_typ") == "M1":
            assert ctx["days_delinquent"] == 30


def test_context_negotiation_history():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ci.get("历史协商情况", "") != "无协商历史"
        assert ctx["has_negotiation_history"] == expected


def test_context_total_debt_parsed():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert ctx["total_debt"] > 0


def test_context_external_debt_parsed():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert ctx["external_debt"] >= 0


def test_context_available_plans():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        for plan in ctx["available_plans"]:
            assert plan in ("reduction", "mina", "installment")
