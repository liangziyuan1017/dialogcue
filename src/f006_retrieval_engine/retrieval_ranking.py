import numpy as np


RANKING_STRATEGY = "limited"


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


def _char_ngrams(text, n=2):
    chars = list(text)
    return ["".join(chars[i:i+n]) for i in range(len(chars) - n + 1)]


def _build_tfidf_vector(text, vocab, idf):
    ngrams = _char_ngrams(text)
    vec = np.zeros(len(vocab))
    for ng in ngrams:
        if ng in vocab:
            vec[vocab[ng]] += 1
    total = vec.sum()
    if total > 0:
        vec /= total
    vec *= idf
    return vec


def compute_context_similarity(current_context, stored_context):
    if not current_context or not stored_context:
        return 0.0
    texts = [current_context, stored_context]
    all_ngrams = [_char_ngrams(t) for t in texts]
    vocab = {}
    for ngrams in all_ngrams:
        for ng in ngrams:
            if ng not in vocab:
                vocab[ng] = len(vocab)
    if not vocab:
        return 0.0
    df = np.zeros(len(vocab))
    for ngrams in all_ngrams:
        seen = set()
        for ng in ngrams:
            if ng not in seen:
                df[vocab[ng]] += 1
                seen.add(ng)
    idf = np.log((2 + 1) / (df + 1)) + 1
    vecs = [_build_tfidf_vector(t, vocab, idf) for t in texts]
    dot = np.dot(vecs[0], vecs[1])
    norm0 = np.linalg.norm(vecs[0])
    norm1 = np.linalg.norm(vecs[1])
    if norm0 == 0 or norm1 == 0:
        return 0.0
    return float(min(max(dot / (norm0 * norm1), 0.0), 1.0))


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


def _rank_limited(pool, conversation_context="", context_missing=False):
    for s in pool:
        if context_missing or not conversation_context:
            s["_sort_primary"] = s.get("win_rate", 0)
            s["_sort_secondary"] = s.get("sas", 0)
            s["_sort_tertiary"] = 0
        else:
            stored = s.get("conversation_context", "")
            if stored and "conversation_context_similarity" not in s:
                s["conversation_context_similarity"] = compute_context_similarity(conversation_context, stored)
            elif "conversation_context_similarity" not in s:
                s["conversation_context_similarity"] = 0.0
            s["_sort_primary"] = s["conversation_context_similarity"]
            s["_sort_secondary"] = s.get("win_rate", 0)
            s["_sort_tertiary"] = s.get("sas", 0)
    pool.sort(key=lambda s: (-s.get("_sort_primary", 0), -s.get("_sort_secondary", 0), -s.get("_sort_tertiary", 0)))
    for s in pool:
        s.pop("_sort_primary", None)
        s.pop("_sort_secondary", None)
        s.pop("_sort_tertiary", None)
    return pool


def _rank_full(pool, conversation_context="", query_bg=None, context_missing=False):
    if query_bg is None:
        query_bg = {}
    for s in pool:
        if not context_missing and conversation_context:
            if "conversation_context_similarity" not in s:
                stored = s.get("conversation_context", "")
                if stored:
                    s["conversation_context_similarity"] = compute_context_similarity(conversation_context, stored)
                else:
                    s["conversation_context_similarity"] = 0.0
        else:
            s["conversation_context_similarity"] = s.get("conversation_context_similarity", 0.0)
        s_bg = s.get("bg_background", {})
        s["_bg_boost"] = compute_bg_boost(s_bg, query_bg)
        s["_sort_primary"] = s.get("win_rate", 0)
        s["_sort_secondary"] = s["conversation_context_similarity"]
        s["_sort_tertiary"] = s.get("sas", 0) + s["_bg_boost"]
    pool.sort(key=lambda s: (-s.get("_sort_primary", 0), -s.get("_sort_secondary", 0), -s.get("_sort_tertiary", 0)))
    for s in pool:
        s.pop("_sort_primary", None)
        s.pop("_sort_secondary", None)
        s.pop("_sort_tertiary", None)
        s.pop("_bg_boost", None)
    return pool


def rank_sentences(pool, strategy=RANKING_STRATEGY, conversation_context="", query_bg=None, context_missing=False):
    if not pool:
        return []
    if strategy == "limited":
        return _rank_limited(list(pool), conversation_context=conversation_context, context_missing=context_missing)
    return _rank_full(list(pool), conversation_context=conversation_context, query_bg=query_bg, context_missing=context_missing)
