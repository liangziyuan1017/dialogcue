from f005_context_scoring.scoring_metrics import (
    encode_bitmask,
    encode_bitmask_int,
)
from f007_infrastructure.embeddings import embed_single


def _extract_bg_constraints_single(profile: dict) -> dict:
    return {
        "has_business_loan": bool(profile.get("has_business_loan")),
        "has_mortgage": bool(profile.get("has_mortgage")),
        "has_other_loan": bool(profile.get("has_other_loan")),
        "recent_repayment": bool(profile.get("recent_repayment")),
        "is_high_risk_proxy_complaint": bool(profile.get("is_high_risk_proxy_complaint")),
        "is_proxy_intermediary_complaint": bool(profile.get("is_proxy_intermediary_complaint")),
        "has_social_insurance": bool(profile.get("has_social_insurance")),
        "has_risk_flag": int(profile.get("risk_level", 0) or 0) > 0,
        "has_complaint": int(profile.get("complaint_score", 0) or 0) > 0,
        "has_vehicle": int(profile.get("vehicle_count", 0) or 0) > 0,
    }


def _extract_bg_background_single(profile: dict) -> dict:
    def _digit_count(n):
        n = abs(int(n or 0))
        return len(str(n)) if n > 0 else 0
    return {
        "business_loan_digits": _digit_count(profile.get("business_loan_balance")),
        "mortgage_balance_digits": _digit_count(profile.get("mortgage_balance")),
        "other_loan_digits": _digit_count(profile.get("other_loan_balance")),
        "wealth_digits": _digit_count(profile.get("wealth_value")),
        "current_balance_digits": _digit_count(profile.get("current_balance")),
        "education": profile.get("education", "unknown"),
        "days_delinquent": int(profile.get("days_delinquent", 0)),
        "recent_contact_count": int(profile.get("recent_contact_count", 0)),
        "risk_level": int(profile.get("risk_level", 0)),
        "complaint_score": int(profile.get("complaint_score", 0)),
    }


def score_new_sentence(
    text: str,
    profile: dict,
    fake_call_id: str,
    turn_index: int,
    node: dict,
) -> dict:
    script_id = f"{fake_call_id}_t{turn_index}"

    bg_constraints = _extract_bg_constraints_single(profile)
    bg_bitmask = encode_bitmask(bg_constraints)
    bg_bitmask_int = encode_bitmask_int(bg_bitmask)

    bg_background = _extract_bg_background_single(profile)

    try:
        embedding = embed_single(text)
    except Exception:
        embedding = None

    existing_pool = node.get("sentence_pool", [])
    win_rate_node = existing_pool[0].get("win_rate_node", 0.5) if existing_pool else 0.5

    branch_key = node.get("branch_key", {})
    collector_action = branch_key.get("action") if isinstance(branch_key, dict) else None
    if not collector_action and existing_pool:
        collector_action = existing_pool[0].get("collector_action")

    sentence = {
        "script_text": text,
        "script_id": script_id,
        "source_call_ids": [fake_call_id],
        "customer_willingness": None,
        "collector_action": collector_action,
        "fact_context": node.get("inherited_facts", []),
        "bg_constraints": bg_constraints,
        "bg_bitmask": bg_bitmask,
        "bg_bitmask_int": bg_bitmask_int,
        "bg_background": bg_background,
        "win_rate": win_rate_node,
        "win_rate_node": win_rate_node,
        "uplift_score": 0,
        "csi": 0,
        "deferred": True,
        "conversation_context": "",
        "sas": 0.0,
    }

    if node.get("role") == "opening" and collector_action == "greeting":
        sentence["gesture_type"] = "opening"

    sentence["_embedding"] = embedding

    return sentence
