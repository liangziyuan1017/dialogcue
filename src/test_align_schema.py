from src.align_schema import align_all, align_record, build_context, build_turns_annotated
from src.load_data import load_records


def _load_labeled():
    import importlib.util
    import os
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "output_labeled.py")
    if not os.path.exists(data_path):
        data_path = os.path.join(os.path.dirname(__file__), "output_labeled.py")
    spec = importlib.util.spec_from_file_location("output_labeled", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


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
        "card_restricted",
        "is_cash_out_customer",
        "external_debt_institutions",
        "interest_ratio",
        "installment_ratio",
        "age",
        "gender",
        "education",
        "industry",
        "has_complaint_history",
        "has_legal_tools",
        "is_negotiation_brain_customer",
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


def test_context_card_restricted():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ci.get("是否管制", "") != "可正常使用卡片"
        assert ctx["card_restricted"] == expected


def test_context_is_cash_out_customer():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ci.get("是否为套现客户", "") != "非套现客户"
        assert ctx["is_cash_out_customer"] == expected


def test_context_external_debt_institutions():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert isinstance(ctx["external_debt_institutions"], int)
        assert ctx["external_debt_institutions"] >= 0


def test_context_interest_ratio():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert 0.0 <= ctx["interest_ratio"] <= 1.0


def test_context_installment_ratio():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert 0.0 <= ctx["installment_ratio"] <= 1.0


def test_context_age():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert isinstance(ctx["age"], int)
        assert ctx["age"] >= 0


def test_context_education():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        assert ctx["education"] in ("unknown", "high_school", "college", "bachelor", "master", "phd", "other")


def test_context_has_complaint_history():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = "没有" not in ci.get("历史投诉情况", "没有")
        assert ctx["has_complaint_history"] == expected


def test_context_has_legal_tools():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ci.get("当前可使用的法务工具", "") != "无可用的法务工具"
        assert ctx["has_legal_tools"] == expected


def test_context_is_negotiation_brain_customer():
    records = load_records()
    for raw in records:
        ci = raw["customer_info"]
        ctx = build_context(ci, raw.get("mob_typ", ""))
        expected = ci.get("是否谈判大脑客户", "") == "Y"
        assert ctx["is_negotiation_brain_customer"] == expected


def test_state_labels_from_output_labeled_carried_into_turns_annotated():
    labeled = _load_labeled()
    aligned = align_all()
    labeled_by_id = {r["call_id"]: r for r in labeled}
    for aln in aligned:
        labeled_rec = labeled_by_id.get(aln["call_id"])
        assert labeled_rec is not None, f"call_id {aln['call_id']} not in output_labeled"
        for turn in aln["turns_annotated"]:
            labeled_turn = labeled_rec["response"]["dialog"][turn["turn_index"]]
            if "state" in labeled_turn:
                assert "state" in turn, f"call_id {aln['call_id']} turn {turn['turn_index']}: state label missing"
                assert turn["state"] == labeled_turn["state"]


def test_state_labels_count_matches_output_labeled():
    labeled = _load_labeled()
    aligned = align_all()
    labeled_by_id = {r["call_id"]: r for r in labeled}
    total_labeled_states = 0
    total_aligned_states = 0
    for aln in aligned:
        labeled_rec = labeled_by_id[aln["call_id"]]
        for t in labeled_rec["response"]["dialog"]:
            if "state" in t:
                total_labeled_states += 1
        for t in aln["turns_annotated"]:
            if "state" in t:
                total_aligned_states += 1
    assert total_aligned_states == total_labeled_states == 493
