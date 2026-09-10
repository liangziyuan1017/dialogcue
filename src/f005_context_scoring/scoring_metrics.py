import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import norm as _sparse_norm
import jieba

from f007_infrastructure.config import get as _cfg

BITMASK_FIELDS = [
    "has_business_loan",
    "has_mortgage",
    "has_other_loan",
    "recent_repayment",
    "is_high_risk_proxy_complaint",
    "is_proxy_intermediary_complaint",
    "has_social_insurance",
    "has_risk_flag",
    "has_complaint",
    "has_vehicle",
]


BG_BACKGROUND_FIELDS = [
    ("business_loan_digits", "business_loan_balance", "digit"),
    ("mortgage_balance_digits", "mortgage_balance", "digit"),
    ("other_loan_digits", "other_loan_balance", "digit"),
    ("wealth_digits", "wealth_value", "digit"),
    ("current_balance_digits", "current_balance", "digit"),
    ("education", "education", "passthrough"),
    ("days_delinquent", "days_delinquent", "int"),
    ("recent_contact_count", "recent_contact_count", "int"),
    ("risk_level", "risk_level", "int"),
    ("complaint_score", "complaint_score", "int"),
]


def _digit_count(value):
    try:
        v = int(value)
    except (ValueError, TypeError):
        return 0
    return len(str(abs(v))) if v > 0 else 0


def _extract_bg_constraints(context):
    return {
        "has_business_loan": bool(context.get("has_business_loan", False)),
        "has_mortgage": bool(context.get("has_mortgage", False)),
        "has_other_loan": bool(context.get("has_other_loan", False)),
        "recent_repayment": bool(context.get("recent_repayment", False)),
        "is_high_risk_proxy_complaint": bool(context.get("is_high_risk_proxy_complaint", False)),
        "is_proxy_intermediary_complaint": bool(context.get("is_proxy_intermediary_complaint", False)),
        "has_social_insurance": bool(context.get("has_social_insurance", False)),
        "has_risk_flag": int(context.get("risk_level", 0) or 0) > 0,
        "has_complaint": int(context.get("complaint_score", 0) or 0) > 0,
        "has_vehicle": int(context.get("vehicle_count", 0) or 0) > 0,
    }


def encode_bitmask(bg_constraints):
    return {field: int(bg_constraints.get(field, False)) for field in BITMASK_FIELDS}


def encode_bitmask_int(bg_bitmask):
    mask = 0
    for i, field in enumerate(BITMASK_FIELDS):
        if bg_bitmask.get(field, 0):
            mask |= (1 << i)
    return mask


def compute_bg_constraints(call_ids, context_lookup):
    if not call_ids:
        return {f: False for f in BITMASK_FIELDS}
    per_source = []
    for cid in call_ids:
        ctx = context_lookup.get(cid)
        if ctx is not None:
            per_source.append(_extract_bg_constraints(ctx))
    if not per_source:
        return {f: False for f in BITMASK_FIELDS}
    result = {}
    for field in BITMASK_FIELDS:
        result[field] = all(src[field] for src in per_source)
    return result


def _extract_bg_background(context):
    result = {}
    for field, source_key, transform in BG_BACKGROUND_FIELDS:
        raw = context.get(source_key)
        if transform == "digit":
            result[field] = _digit_count(raw)
        elif transform == "int":
            try:
                result[field] = int(raw) if raw is not None else 0
            except (ValueError, TypeError):
                result[field] = 0
        else:
            result[field] = raw if raw is not None else ""
    return result


def _bg_background_default():
    return {field: (0 if t in ("digit", "int") else "") for field, _, t in BG_BACKGROUND_FIELDS}


def compute_bg_background(call_ids, context_lookup):
    if not call_ids:
        return _bg_background_default()
    per_source = []
    for cid in call_ids:
        ctx = context_lookup.get(cid)
        if ctx is not None:
            per_source.append(_extract_bg_background(ctx))
    if not per_source:
        return _bg_background_default()
    result = {}
    for field, _, transform in BG_BACKGROUND_FIELDS:
        values = [src[field] for src in per_source]
        if transform == "passthrough":
            uniq = [v for v in values if v != ""]
            if not uniq:
                result[field] = ""
            elif len(set(uniq)) == 1:
                result[field] = uniq[0]
            else:
                result[field] = ", ".join(sorted(str(v) for v in set(uniq)))
        else:
            result[field] = max(values)
    return result


def compute_hwr(call_ids, reward_lookup):
    if not call_ids:
        return _cfg("hwr.default", 0.5)
    alpha = _cfg("hwr.laplace_alpha", 1)
    beta = _cfg("hwr.laplace_beta", 2)
    wins = sum(1 for cid in call_ids if reward_lookup.get(cid) == 1)
    total = len(call_ids)
    return (wins + alpha) / (total + beta)


def compute_node_hwr(sentence_pool, reward_lookup):
    all_call_ids = set()
    for s in sentence_pool:
        all_call_ids.update(s.get("source_call_ids", []))
    if not all_call_ids:
        return _cfg("hwr.default", 0.5)
    alpha = _cfg("hwr.laplace_alpha", 1)
    beta = _cfg("hwr.laplace_beta", 2)
    wins = sum(1 for cid in all_call_ids if reward_lookup.get(cid) == 1)
    total = len(all_call_ids)
    return (wins + alpha) / (total + beta)


def cosine_similarity(a, b):
    a = np.array(a, dtype=np.float64)
    b = np.array(b, dtype=np.float64)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _word_ngrams(text, n=2):
    words = list(jieba.cut(text))
    words = [w.strip() for w in words if w.strip()]
    if n == 1:
        return words
    result = []
    for i in range(len(words) - n + 1):
        result.append("".join(words[i:i+n]))
    if not result and words:
        result = words
    return result


def compute_sas_for_pool(sentences, embeddings_map=None):
    ngram_n = _cfg("sas.ngram_size", 2)
    if len(sentences) <= 1:
        return [1.0] * len(sentences)
    texts = [s.get("script_text", "") for s in sentences]
    ref_idx = max(range(len(sentences)), key=lambda i: sentences[i].get("win_rate", 0))
    ref_ngrams = set(_word_ngrams(texts[ref_idx], ngram_n))
    vocab = {ng: i for i, ng in enumerate(sorted(ref_ngrams))}
    n_vocab = len(vocab)
    if n_vocab == 0:
        return [0.0] * len(sentences)
    n_docs = len(texts)
    doc_ngrams = []
    for t in texts:
        ngrams = _word_ngrams(t, ngram_n)
        doc_ngrams.append([ng for ng in ngrams if ng in vocab])
    df = np.zeros(n_vocab)
    for ngrams in doc_ngrams:
        for ng in set(ngrams):
            df[vocab[ng]] += 1
    idf = np.log((n_docs + 1) / (df + 1)) + 1
    rows, cols, data = [], [], []
    for i, ngrams in enumerate(doc_ngrams):
        counts = {}
        for ng in ngrams:
            counts[vocab[ng]] = counts.get(vocab[ng], 0) + 1
        for col, cnt in counts.items():
            rows.append(i)
            cols.append(col)
            data.append(cnt)
    if not data:
        return [0.0] * len(sentences)
    counts_mat = csr_matrix((data, (rows, cols)), shape=(n_docs, n_vocab), dtype=np.float64)
    norms = counts_mat.sum(axis=1)
    norms[norms == 0] = 1
    tf = counts_mat.multiply(1.0 / norms)
    tfidf = tf.multiply(idf).tocsr()
    ref_vec = tfidf[ref_idx]
    ref_norm = float(_sparse_norm(ref_vec))
    row_norms = _sparse_norm(tfidf, axis=1).ravel()
    dots = tfidf.dot(ref_vec.T).toarray().ravel()
    scores = []
    for i in range(len(sentences)):
        if ref_norm == 0.0 or row_norms[i] == 0.0:
            scores.append(0.0)
            continue
        sim = float(dots[i]) / (ref_norm * float(row_norms[i]))
        scores.append(float(min(max(sim, 0.0), 1.0)))
    return scores
