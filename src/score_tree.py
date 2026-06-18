import importlib.util
import json
import os

import numpy as np


def _load_py(filepath):
    spec = importlib.util.spec_from_file_location("mod", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_output_aligned():
    path = os.path.join(os.path.dirname(__file__), "output_aligned.py")
    return _load_py(path).results


def _load_output_rewarded():
    path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    return _load_py(path).results


def _load_decision_tree():
    path = os.path.join(os.path.dirname(__file__), "decision_tree.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_context_lookup(records=None):
    if records is None:
        records = _load_output_aligned()
    return {r["call_id"]: r["context"] for r in records}


def build_customer_info_lookup(records=None):
    if records is None:
        records = _load_output_aligned()
    return {r["call_id"]: r.get("customer_info", {}) for r in records}


def build_reward_lookup(records=None):
    if records is None:
        records = _load_output_rewarded()
    return {r["call_id"]: r["reward"] for r in records}


BITMASK_FIELDS = [
    "has_auto_loan",
    "has_mortgage",
    "has_negotiation_history",
    "social_insurance_stable",
    "credit_rating_good",
]


def _extract_bg_constraints(context):
    return {
        "has_auto_loan": bool(context.get("has_auto_loan", False)),
        "has_mortgage": bool(context.get("has_mortgage", False)),
        "has_negotiation_history": bool(context.get("has_negotiation_history", False)),
        "social_insurance_stable": bool(context.get("social_insurance_stable", False)),
        "credit_rating_good": context.get("credit_rating") == "good",
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


BG_BACKGROUND_FIELDS = [
    ("age", "年龄"),
    ("gender", "性别"),
    ("education", "学历"),
    ("industry", "行业"),
    ("is_cash_out", "是否为套现客户"),
    ("is_restricted", "是否管制"),
    ("complaint_history", "历史投诉情况"),
]


def _extract_bg_background(customer_info):
    result = {}
    for eng_key, cn_key in BG_BACKGROUND_FIELDS:
        result[eng_key] = customer_info.get(cn_key, "")
    return result


def compute_bg_background(call_ids, customer_info_lookup):
    if not call_ids:
        return {eng: "" for eng, _ in BG_BACKGROUND_FIELDS}
    per_source = []
    for cid in call_ids:
        ci = customer_info_lookup.get(cid)
        if ci is not None:
            per_source.append(_extract_bg_background(ci))
    if not per_source:
        return {eng: "" for eng, _ in BG_BACKGROUND_FIELDS}
    result = {}
    for eng_key, _ in BG_BACKGROUND_FIELDS:
        values = [src[eng_key] for src in per_source if src[eng_key] != ""]
        result[eng_key] = values[0] if len(set(values)) == 1 else ", ".join(sorted(set(values)))
    return result


def compute_hwr(call_ids, reward_lookup):
    if not call_ids:
        return 0.5
    wins = sum(1 for cid in call_ids if reward_lookup.get(cid) == 1)
    total = len(call_ids)
    return (wins + 1) / (total + 2)


def cosine_similarity(a, b):
    a = np.array(a, dtype=np.float64)
    b = np.array(b, dtype=np.float64)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _char_ngrams(text, n=2):
    chars = list(text)
    return ["".join(chars[i:i+n]) for i in range(len(chars) - n + 1)]


def _build_tfidf_matrix(texts, ngram_range=2):
    doc_ngrams = [_char_ngrams(t, ngram_range) for t in texts]
    vocab = {}
    for ngrams in doc_ngrams:
        for ng in ngrams:
            if ng not in vocab:
                vocab[ng] = len(vocab)
    n_docs = len(texts)
    df = np.zeros(len(vocab))
    for ngrams in doc_ngrams:
        seen = set()
        for ng in ngrams:
            if ng not in seen:
                df[vocab[ng]] += 1
                seen.add(ng)
    idf = np.log((n_docs + 1) / (df + 1)) + 1
    matrix = np.zeros((n_docs, len(vocab)))
    for i, ngrams in enumerate(doc_ngrams):
        for ng in ngrams:
            matrix[i, vocab[ng]] += 1
    norms = matrix.sum(axis=1, keepdims=True)
    norms[norms == 0] = 1
    tf = matrix / norms
    tfidf = tf * idf
    return tfidf


def compute_sas_for_pool(sentences, embeddings_map=None):
    if len(sentences) <= 1:
        return [1.0] * len(sentences)
    texts = [s.get("script_text", "") for s in sentences]
    tfidf = _build_tfidf_matrix(texts)
    ref_idx = max(range(len(sentences)), key=lambda i: sentences[i].get("win_rate", 0))
    ref_vec = tfidf[ref_idx]
    scores = []
    for i in range(len(sentences)):
        sim = cosine_similarity(ref_vec, tfidf[i])
        scores.append(min(max(sim, 0.0), 1.0))
    return scores


def _score_sentence_pool(sentence_pool, context_lookup, reward_lookup, customer_info_lookup):
    for s in sentence_pool:
        call_ids = s.get("source_call_ids", [])
        bg = compute_bg_constraints(call_ids, context_lookup)
        s["bg_constraints"] = bg
        bg_bitmask = encode_bitmask(bg)
        s["bg_bitmask"] = bg_bitmask
        s["bg_bitmask_int"] = encode_bitmask_int(bg_bitmask)
        s["bg_background"] = compute_bg_background(call_ids, customer_info_lookup)
        s["win_rate"] = compute_hwr(call_ids, reward_lookup)
        s["uplift_score"] = 0
        s["csi"] = 0
        s["deferred"] = True
    sas_scores = compute_sas_for_pool(sentence_pool)
    for s, sas in zip(sentence_pool, sas_scores):
        s["sas"] = sas
    return sentence_pool


def score_tree(tree, context_lookup, reward_lookup, customer_info_lookup):
    def _walk(node):
        _score_sentence_pool(
            node.get("sentence_pool", []),
            context_lookup,
            reward_lookup,
            customer_info_lookup,
        )
        for child in node.get("children", []):
            _walk(child)

    _walk(tree)
    return tree


def write_scored_tree(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "decision_tree_scored.json")
    tree = _load_decision_tree()
    context_lookup = build_context_lookup()
    reward_lookup = build_reward_lookup()
    customer_info_lookup = build_customer_info_lookup()
    scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    return scored


if __name__ == "__main__":
    scored = write_scored_tree()
    print(f"Wrote scored tree to decision_tree_scored.json")
