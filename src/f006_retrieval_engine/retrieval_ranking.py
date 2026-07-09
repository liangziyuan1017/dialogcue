import numpy as np

from f005_context_scoring.scoring_metrics import BITMASK_FIELDS  # noqa: F401  (re-exported)
from f007_infrastructure.config import get as _cfg


def _load_ranking_weights():
    return {
        "win_rate": _cfg("ranking_weights.win_rate", 0.35),
        "vec_score": _cfg("ranking_weights.vec_score", 0.25),
        "sas": _cfg("ranking_weights.sas", 0.10),
        "bg_boost": _cfg("ranking_weights.bg_boost", 0.10),
        "bitmask_score": _cfg("ranking_weights.bitmask_score", 0.20),
    }


def get_ranking_weights():
    return _load_ranking_weights()


RANKING_WEIGHTS = _load_ranking_weights()


async def compute_vec_similarity(query_vec: list[float], candidate_script_ids: list[str], db) -> dict[str, float]:
    if not candidate_script_ids:
        return {}
    candidate_vecs = await db.get_vectors(candidate_script_ids)
    query = np.array(query_vec, dtype=np.float32)
    q_norm = float(np.linalg.norm(query))
    scores = {}
    for sid, vec in candidate_vecs.items():
        v = np.array(vec, dtype=np.float32)
        dot = float(np.dot(query, v))
        if q_norm > 0:
            v_norm = float(np.linalg.norm(v))
            scores[sid] = float(dot / (q_norm * v_norm)) if v_norm > 0 else 0.0
        else:
            scores[sid] = 0.0
    return scores


def _first_val(val):
    if isinstance(val, str) and "," in val:
        return val.split(",")[0].strip()
    return val


def compute_bg_boost(sentence_bg, query_bg):
    boost = 0.0
    if isinstance(sentence_bg, str):
        sentence_bg = {}
    s_edu = _first_val(sentence_bg.get("education", ""))
    q_edu = query_bg.get("education", "")
    if s_edu and q_edu and s_edu == q_edu:
        boost += _cfg("bg_boost.education_match", 0.02)
    s_risk = _safe_int(sentence_bg.get("risk_level", 0))
    q_risk = _safe_int(query_bg.get("risk_level", 0))
    if s_risk > 0 and q_risk > 0 and s_risk == q_risk:
        boost += _cfg("bg_boost.risk_level_match", 0.03)
    s_complaint = _safe_int(sentence_bg.get("complaint_score", 0))
    q_complaint = _safe_int(query_bg.get("complaint_score", 0))
    complaint_threshold = _cfg("bg_boost.complaint_proximity_threshold", 5)
    if s_complaint > 0 and q_complaint > 0 and abs(s_complaint - q_complaint) <= complaint_threshold:
        boost += _cfg("bg_boost.complaint_proximity_match", 0.02)
    s_delinquent = _safe_int(sentence_bg.get("days_delinquent", 0))
    q_delinquent = _safe_int(query_bg.get("days_delinquent", 0))
    delinquent_threshold = _cfg("bg_boost.delinquent_proximity_threshold", 30)
    if s_delinquent > 0 and q_delinquent > 0 and abs(s_delinquent - q_delinquent) <= delinquent_threshold:
        boost += _cfg("bg_boost.delinquent_proximity_match", 0.02)
    q_recent_contact = _safe_int(query_bg.get("recent_contact_count", 0))
    if q_recent_contact > 0:
        boost += _cfg("bg_boost.recent_contact_signal", 0.02)
    for digits_field in ("current_balance_digits", "wealth_digits", "business_loan_digits",
                         "mortgage_balance_digits", "other_loan_digits"):
        s_d = _safe_int(sentence_bg.get(digits_field, 0))
        q_d = _safe_int(query_bg.get(digits_field, 0))
        digits_threshold = _cfg("bg_boost.digits_proximity_threshold", 1)
        if s_d > 0 and q_d > 0 and abs(s_d - q_d) <= digits_threshold:
            boost += _cfg("bg_boost.digits_proximity_match", 0.01)
    return boost


def _safe_int(val):
    try:
        if isinstance(val, str):
            val = val.split(",")[0].strip().rstrip("%")
        return int(val)
    except (ValueError, TypeError):
        return 0


async def rank_sentences(pool, query_vec=None, db=None, query_bg=None, conversation_context="", context_missing=False):
    if not pool:
        return []
    pool = list(pool)
    if query_bg is None:
        query_bg = {}

    weights = get_ranking_weights()

    script_ids = [s.get("script_id", "") for s in pool]
    vec_scores = {}
    if query_vec is not None and db is not None and script_ids:
        vec_scores = await compute_vec_similarity(query_vec, script_ids, db)

    for s in pool:
        sid = s.get("script_id", "")
        s["vec_score"] = float(vec_scores.get(sid, 0.0))
        s_bg = s.get("bg_background", {}) or {}
        bg_boost = compute_bg_boost(s_bg, query_bg)
        s["_bg_boost_val"] = bg_boost
        bitmask_score = s.pop("_bitmask_score", 1.0)
        s["bitmask_score"] = bitmask_score
        s["final_score"] = float(
            weights["win_rate"] * s.get("win_rate", 0)
            + weights["vec_score"] * s["vec_score"]
            + weights["sas"] * s.get("sas", 0)
            + weights["bg_boost"] * bg_boost
            + weights["bitmask_score"] * bitmask_score
        )

    pool.sort(key=lambda s: -s.get("final_score", 0))

    for s in pool:
        s.pop("_bg_boost_val", None)

    return pool
