from f001_schema_alignment.align_schema import align_all

NEW_CONTEXT_KEYS = {
    "business_loan_balance", "complaint_score", "current_balance",
    "days_delinquent", "education", "has_business_loan", "has_mortgage",
    "has_other_loan", "has_social_insurance", "is_high_risk_proxy_complaint",
    "is_proxy_intermediary_complaint", "mortgage_balance", "other_loan_balance",
    "recent_contact_count", "recent_repayment", "risk_level", "vehicle_count",
    "wealth_value",
}


def test_all_context_fields_populated():
    aligned = align_all()
    for rec in aligned:
        assert set(rec["context"].keys()) == NEW_CONTEXT_KEYS
        for k in NEW_CONTEXT_KEYS:
            assert rec["context"][k] is not None, f"{rec['call_id']}: context.{k} is None"


def test_context_no_nulls_in_required_fields():
    aligned = align_all()
    for rec in aligned:
        ctx = rec["context"]
        assert isinstance(ctx["has_business_loan"], bool)
        assert isinstance(ctx["has_mortgage"], bool)
        assert isinstance(ctx["has_other_loan"], bool)
        assert isinstance(ctx["days_delinquent"], int)
        assert isinstance(ctx["current_balance"], int)
        assert isinstance(ctx["has_social_insurance"], bool)
        assert isinstance(ctx["is_high_risk_proxy_complaint"], bool)
        assert isinstance(ctx["is_proxy_intermediary_complaint"], bool)
        assert isinstance(ctx["risk_level"], int)
        assert isinstance(ctx["complaint_score"], int)
        assert isinstance(ctx["education"], str)
        assert isinstance(ctx["recent_contact_count"], int)
        assert isinstance(ctx["recent_repayment"], bool)
        assert isinstance(ctx["business_loan_balance"], int)
        assert isinstance(ctx["mortgage_balance"], int)
        assert isinstance(ctx["other_loan_balance"], int)
        assert isinstance(ctx["vehicle_count"], int)
        assert isinstance(ctx["wealth_value"], int)


def test_context_has_business_loan():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["has_business_loan"], bool)


def test_context_has_mortgage():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["has_mortgage"], bool)


def test_context_risk_level():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["risk_level"], int)
        assert rec["context"]["risk_level"] >= 0


def test_context_days_delinquent():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["days_delinquent"], int)
        assert rec["context"]["days_delinquent"] >= 0


def test_context_education():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["education"], str)


def test_context_complaint_score():
    aligned = align_all()
    for rec in aligned:
        assert isinstance(rec["context"]["complaint_score"], int)
        assert rec["context"]["complaint_score"] >= 0
