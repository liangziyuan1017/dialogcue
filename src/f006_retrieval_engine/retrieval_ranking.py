import numpy as np


RANKING_WEIGHTS = {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15}


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
]

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
]


def compute_vec_similarity(query_vec: list[float], candidate_script_ids: list[str], db) -> dict[str, float]:
    if not candidate_script_ids:
        return {}
    candidate_vecs = db.get_vectors(candidate_script_ids)
    query = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(query)
    scores = {}
    for sid, vec in candidate_vecs.items():
        v = np.array(vec, dtype=np.float32)
        dot = float(np.dot(query, v))
        v_norm = float(np.linalg.norm(v))
        scores[sid] = dot / (q_norm * v_norm) if q_norm > 0 and v_norm > 0 else 0.0
    return scores


def compute_bg_boost(sentence_bg, query_bg):
    boost = 0.0
    if sentence_bg.get("industry") and query_bg.get("industry"):
        if sentence_bg["industry"] == query_bg["industry"]:
            boost += 0.05
    if sentence_bg.get("education") and query_bg.get("education"):
        if sentence_bg["education"] == query_bg["education"]:
            boost += 0.02
    s_debt = _safe_int(sentence_bg.get("total_debt", 0))
    q_debt = _safe_int(query_bg.get("total_debt", 0))
    if s_debt > 0 and q_debt > 0:
        ratio = max(s_debt, q_debt) / min(s_debt, q_debt)
        if ratio <= 1.5:
            boost += 0.03
    s_age = _safe_int(sentence_bg.get("age", 0))
    q_age = _safe_int(query_bg.get("age", 0))
    if s_age > 0 and q_age > 0 and abs(s_age - q_age) <= 10:
        boost += 0.02
    return boost


def _safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def rank_sentences(pool, query_vec=None, db=None, query_bg=None, conversation_context="", context_missing=False):
    if not pool:
        return []
    pool = list(pool)
    if query_bg is None:
        query_bg = {}

    script_ids = [s.get("script_id", "") for s in pool]
    vec_scores = {}
    if query_vec is not None and db is not None and script_ids:
        vec_scores = compute_vec_similarity(query_vec, script_ids, db)

    for s in pool:
        sid = s.get("script_id", "")
        s["vec_score"] = vec_scores.get(sid, 0.0)
        s_bg = s.get("bg_background", {}) or {}
        bg_boost = compute_bg_boost(s_bg, query_bg)
        s["_bg_boost_val"] = bg_boost
        s["final_score"] = (
            RANKING_WEIGHTS["win_rate"] * s.get("win_rate", 0)
            + RANKING_WEIGHTS["vec_score"] * s["vec_score"]
            + RANKING_WEIGHTS["sas"] * s.get("sas", 0)
            + RANKING_WEIGHTS["bg_boost"] * bg_boost
        )

    pool.sort(key=lambda s: -s.get("final_score", 0))

    for s in pool:
        s.pop("_bg_boost_val", None)

    return pool
