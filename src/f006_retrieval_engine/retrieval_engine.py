import json
import os
from collections import defaultdict

from .retrieval_ranking import (
    BITMASK_FIELDS,
    BG_BACKGROUND_FIELDS,
    RANKING_WEIGHTS,
    compute_bg_boost,
    rank_sentences,
)


def _load_scored_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "decision_tree_scored.json")
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


def recommend(inherited_facts, branch_key_values, query_bitmask, conversation_context, query_bg,
              tree=None, index=None, keyword_freq=None, db=None, query_vec=None,
              conversation_state=None):
    if tree is None:
        tree = _load_scored_tree()
    if index is None:
        index = build_node_index(tree)
    if keyword_freq is None:
        keyword_freq = _compute_keyword_freq(index)
    if conversation_state is None:
        conversation_state = {"facts": [], "emotions": [], "actions": []}

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

    if db is not None and nodes:
        first_node = nodes[0]
        node_id = first_node.get("_db_node_id", 1)
        pool = db.get_sentences_by_node(node_id)
    else:
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

    ranked = rank_sentences(filtered, query_vec=query_vec, db=db,
                            query_bg=query_bg,
                            conversation_context=conversation_context,
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
        "vec_score": top.get("vec_score", 0),
        "final_score": top.get("final_score", 0),
        "confidence": round(confidence_val, 2),
        "ranking_weights": RANKING_WEIGHTS,
        "fallbacks": fallbacks,
        "conversation_state": conversation_state,
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
        tree=tree, index=index, keyword_freq=keyword_freq,
    )
    if result:
        print(f"Recommend: {result['script_id']} (confidence={result['confidence']}, final_score={result['final_score']:.4f})")
    else:
        print("No recommendation")
