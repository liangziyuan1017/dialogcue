import json
import os
from collections import defaultdict

import numpy as np


RANKING_STRATEGY = "limited"


def _load_scored_tree():
    path = os.path.join(os.path.dirname(__file__), "decision_tree_scored.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _flatten_branch_key(branch_key):
    vals = []
    for k, v in branch_key.items():
        if isinstance(v, list):
            vals.extend(v)
        else:
            vals.append(v)
    return vals


def _compute_key(inherited_facts, branch_key_values):
    return (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)))


def build_node_index(tree):
    index = defaultdict(list)
    def walk(node):
        facts = node.get("inherited_facts", [])
        bk_vals = _flatten_branch_key(node.get("branch_key", {}))
        key = _compute_key(facts, bk_vals)
        index[key].append(node)
        for child in node.get("children", []):
            walk(child)
    walk(tree)
    return dict(index)


def _compute_keyword_freq(index):
    freq = {}
    for (facts, bk), nodes in index.items():
        for kw in facts + bk:
            freq[kw] = freq.get(kw, 0) + 1
    return freq


def lookup_by_key(inherited_facts, branch_key_values, index):
    key = _compute_key(inherited_facts, branch_key_values)
    return index.get(key, [])


def aggregate_pools(nodes):
    pool = []
    for node in nodes:
        pool.extend(node.get("sentence_pool", []))
    return pool


def lookup_with_fallback(inherited_facts, branch_key_values, index, keyword_freq):
    confidence = 1.0
    fallbacks = []
    facts = list(inherited_facts)
    bk = list(branch_key_values)

    while True:
        nodes = lookup_by_key(facts, bk, index)
        if nodes:
            return nodes, confidence, fallbacks
        if not facts:
            nodes = lookup_by_key([], bk, index)
            if nodes:
                return nodes, confidence, fallbacks
            return [], confidence, fallbacks
        least = min(facts, key=lambda f: keyword_freq.get(f, 0))
        facts.remove(least)
        confidence -= 0.1
        fallbacks.append("key_drop")


def descend_for_sentences(nodes):
    pool = []
    for node in nodes:
        pool.extend(node.get("sentence_pool", []))
    if pool:
        return pool, 1.0, []

    confidence = 1.0
    fallbacks = []
    current = list(nodes)

    while True:
        next_level = []
        for node in current:
            for child in node.get("children", []):
                next_level.append(child)
        if not next_level:
            return [], confidence, fallbacks
        confidence -= 0.05
        fallbacks.append("descend")
        pool = []
        for node in next_level:
            pool.extend(node.get("sentence_pool", []))
        if pool:
            return pool, confidence, fallbacks
        current = next_level


def filter_by_bitmask(pool, query_bitmask):
    return [s for s in pool if (s.get("bg_bitmask_int", 0) & query_bitmask) == s.get("bg_bitmask_int", 0)]


def relax_bitmask(pool, query_bitmask):
    fallbacks = []
    relaxations = 0
    mask = query_bitmask
    while mask > 0:
        lowest_bit = mask & (-mask)
        mask &= ~lowest_bit
        relaxations += 1
        fallbacks.append("bitmask_relax")
        result = filter_by_bitmask(pool, mask)
        if result:
            return result, relaxations, fallbacks
    result = filter_by_bitmask(pool, 0)
    if result:
        return result, relaxations, fallbacks
    return [], relaxations, fallbacks


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


def recommend(inherited_facts, branch_key_values, query_bitmask, conversation_context, query_bg, strategy=RANKING_STRATEGY, tree=None, index=None, keyword_freq=None):
    if tree is None:
        tree = _load_scored_tree()
    if index is None:
        index = build_node_index(tree)
    if keyword_freq is None:
        keyword_freq = _compute_keyword_freq(index)

    confidence = 1.0
    fallbacks = []

    context_missing = not conversation_context
    if context_missing:
        confidence -= 0.1
        fallbacks.append("context_missing")

    nodes, n_conf, n_fb = lookup_with_fallback(inherited_facts, branch_key_values, index, keyword_freq)
    confidence = min(confidence, n_conf) if n_conf < 1.0 else confidence
    if n_conf < 1.0:
        confidence = 1.0
        fallbacks = list(n_fb)
        if context_missing:
            confidence -= 0.1
            fallbacks.insert(0, "context_missing")

    if not nodes:
        return None

    pool = aggregate_pools(nodes)

    if not pool:
        d_pool, d_conf, d_fb = descend_for_sentences(nodes)
        fallbacks.extend(d_fb)
        if not d_pool:
            facts = list(inherited_facts)
            while facts:
                least = min(facts, key=lambda f: keyword_freq.get(f, 0))
                facts.remove(least)
                fallbacks.append("key_drop")
                nodes2 = lookup_by_key(facts, branch_key_values, index)
                if nodes2:
                    pool = aggregate_pools(nodes2)
                    if pool:
                        break
                    d_pool2, _, d_fb2 = descend_for_sentences(nodes2)
                    fallbacks.extend(d_fb2)
                    if d_pool2:
                        pool = d_pool2
                        break
            if not pool:
                return None
        else:
            pool = d_pool

    filtered = filter_by_bitmask(pool, query_bitmask)
    if not filtered:
        filtered, relaxations, r_fb = relax_bitmask(pool, query_bitmask)
        fallbacks.extend(r_fb)
        if not filtered:
            return None

    ranked = rank_sentences(filtered, strategy=strategy,
                            conversation_context=conversation_context,
                            query_bg=query_bg,
                            context_missing=context_missing)

    if not ranked:
        return None

    top = ranked[0]
    confidence_val = 1.0
    confidence_val -= fallbacks.count("key_drop") * 0.1
    confidence_val -= fallbacks.count("descend") * 0.05
    confidence_val -= fallbacks.count("bitmask_relax") * 0.05
    confidence_val -= fallbacks.count("context_missing") * 0.1
    confidence_val = max(confidence_val, 0.0)

    return {
        "script_text": top.get("script_text", ""),
        "script_id": top.get("script_id", ""),
        "state_id": top.get("state_id", ""),
        "win_rate": top.get("win_rate", 0),
        "sas": top.get("sas", 0),
        "conversation_context_similarity": top.get("conversation_context_similarity", 0),
        "confidence": round(confidence_val, 2),
        "strategy": strategy,
        "fallbacks": fallbacks,
    }


if __name__ == "__main__":
    tree = _load_scored_tree()
    index = build_node_index(tree)
    keyword_freq = _compute_keyword_freq(index)
    print(f"Index: {len(index)} keys, {sum(len(v) for v in index.values())} nodes")
    result = recommend(
        inherited_facts=["financial_hardship"],
        branch_key_values=["empathy"],
        query_bitmask=0,
        conversation_context="客户说没有钱",
        query_bg={},
        strategy="limited",
        tree=tree, index=index, keyword_freq=keyword_freq,
    )
    if result:
        print(f"Recommend: {result['script_id']} (confidence={result['confidence']}, fallbacks={result['fallbacks']})")
    else:
        print("No recommendation")
