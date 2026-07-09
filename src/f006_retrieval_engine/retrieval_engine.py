import json
import os
from collections import defaultdict
from itertools import combinations

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.logging import get_logger as _get_logger

from .retrieval_ranking import (
    get_ranking_weights,
    rank_sentences,
)

_log = _get_logger(__name__)

def _pool_cap():
    return _cfg("pool_cap", 50)


POOL_CAP = _pool_cap()


def _load_scored_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "data", "decision_tree_scored.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compute_key(inherited_facts, branch_key_values, inherited_emotions=None):
    if inherited_emotions is None:
        inherited_emotions = []
    return (tuple(sorted(inherited_facts)), tuple(sorted(branch_key_values)), tuple(sorted(inherited_emotions)))


def _flatten_branch_key(branch_key):
    vals = []
    for _k, v in branch_key.items():
        if isinstance(v, list):
            vals.extend(v)
        else:
            vals.append(v)
    return vals


def build_node_index(tree):
    index = defaultdict(list)
    def walk(node):
        facts = node.get("inherited_facts", [])
        bk_vals = _flatten_branch_key(node.get("branch_key", {}))
        emotions = node.get("inherited_emotions", [])
        key = _compute_key(facts, bk_vals, emotions)
        index[key].append(node)
        for child in node.get("children") or []:
            walk(child)
    walk(tree)
    return dict(index)


def _build_label_set_index(index):
    label_to_nodes = {}
    for key, nodes in index.items():
        label_set = frozenset(key[0] + key[1] + key[2])
        label_to_nodes.setdefault(label_set, []).extend(nodes)
    return label_to_nodes


def _build_reverse_index(index):
    keyword_to_keys = defaultdict(set)
    for key in index:
        for kw in key[0] + key[1] + key[2]:
            keyword_to_keys[kw].add(key)
    return dict(keyword_to_keys)


def aggregate_pools(nodes):
    pool = []
    for node in nodes:
        pool.extend(node.get("sentence_pool", []))
    return pool


def _has_reachable_sentences(nodes):
    pool, _, _ = descend_for_sentences(nodes)
    return bool(pool)


def _find_matching_nodes_subset(all_facts, all_emotions, all_actions, index, label_set_index, pool_cap=None):
    if pool_cap is None:
        pool_cap = _pool_cap()
    all_facts = list(all_facts)
    all_emotions = list(all_emotions)
    all_actions = list(all_actions)

    query_items = frozenset(all_facts + all_emotions + all_actions)

    if query_items and query_items in label_set_index:
        nodes = label_set_index[query_items]
        if _has_reachable_sentences(nodes):
            return nodes, 1.0, []

    drop_order = []
    n_emo = len(all_emotions)
    n_fact = len(all_facts)
    for total_dropped in range(1, n_emo + n_fact + 1):
        for n_drop_e in range(min(total_dropped, n_emo), -1, -1):
            n_drop_f = total_dropped - n_drop_e
            if n_drop_f < 0 or n_drop_f > n_fact:
                continue
            drop_order.append((n_drop_e, n_drop_f))

    max_combos = _cfg("decision_tree.max_subset_combinations", 4096)
    combo_count = 0
    truncated = False
    for n_drop_e, n_drop_f in drop_order:
        found_nodes = []
        keep_e = n_emo - n_drop_e
        keep_f = n_fact - n_drop_f

        for emo_subset in combinations(all_emotions, keep_e):
            for fact_subset in combinations(all_facts, keep_f):
                combo_count += 1
                if combo_count > max_combos:
                    truncated = True
                    break
                label_set = frozenset(fact_subset) | frozenset(emo_subset) | frozenset(all_actions)
                if label_set in label_set_index:
                    found_nodes.extend(label_set_index[label_set])
            if truncated:
                break

        if found_nodes:
            seen_ids = set()
            unique = []
            for n in found_nodes:
                sid = n.get("state_id", str(id(n)))
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    unique.append(n)

            pool = aggregate_pools(unique)
            if not pool:
                pool, _, _ = descend_for_sentences(unique)
            if pool and len(pool) <= pool_cap:
                    n_dropped = n_drop_e + n_drop_f
                    conf = max(0.0, 1.0 - n_dropped * _cfg("confidence.subset_drop_penalty", 0.1))
                    fb = ["subset_drop_emotion"] * n_drop_e + ["subset_drop_fact"] * n_drop_f
                    if truncated:
                        fb.append("subset_search_truncated")
                    return unique, conf, fb
        if truncated:
            break

    root_nodes = label_set_index.get(frozenset(), [])
    if root_nodes and _has_reachable_sentences(root_nodes):
        fb = ["root_fallback"]
        if truncated:
            fb.append("subset_search_truncated")
        return root_nodes, _cfg("confidence.root_fallback", 0.2), fb
    fb = ["no_match"]
    if truncated:
        fb.append("subset_search_truncated")
    return [], 0.0, fb


def descend_for_sentences(nodes):
    pool = []
    for node in nodes:
        pool.extend(node.get("sentence_pool", []))
    if pool:
        return pool, 1.0, []

    confidence = 1.0
    fallbacks = []
    current = list(nodes)
    max_levels = _cfg("decision_tree.find_node_max_levels", 4)
    level = 0

    while level < max_levels:
        next_level = []
        for node in current:
            for child in node.get("children") or []:
                next_level.append(child)
        if not next_level:
            return [], confidence, fallbacks
        confidence = max(0.0, confidence - _cfg("confidence.descend_penalty", 0.05))
        fallbacks.append("descend")
        pool = []
        for node in next_level:
            pool.extend(node.get("sentence_pool", []))
        if pool:
            return pool, confidence, fallbacks
        current = next_level
        level += 1
    return [], confidence, fallbacks


def _bit_count(n):
    c = 0
    while n:
        c += 1
        n &= n - 1
    return c


def compute_bitmask_score(sentence_bitmask, query_bitmask):
    if sentence_bitmask == 0:
        return 1.0
    if query_bitmask == 0:
        return 0.5
    matched = sentence_bitmask & query_bitmask
    required_bits = _bit_count(sentence_bitmask)
    matched_bits = _bit_count(matched)
    return matched_bits / required_bits


async def recommend(query_bitmask, conversation_context, query_bg,
              tree=None, index=None, db=None, query_vec=None,
              conversation_state=None, label_set_index=None):
    if tree is None:
        tree = _load_scored_tree()
    if index is None:
        index = build_node_index(tree)
    if label_set_index is None:
        label_set_index = _build_label_set_index(index)

    from f008_state_extraction.state_extraction import flat_to_path_state, path_state_to_flat

    if conversation_state is None:
        conversation_state = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}

    if "branch_key" in conversation_state:
        all_facts, all_emotions, all_actions = path_state_to_flat(conversation_state)
        path_state = conversation_state
    else:
        all_facts = conversation_state.get("facts", [])
        all_emotions = conversation_state.get("emotions", [])
        all_actions = conversation_state.get("actions", [])
        path_state = flat_to_path_state(all_facts, all_emotions, all_actions, conversation_state.get("willingness"))

    composite_state_id = "|".join(all_facts + all_emotions + all_actions)

    fallbacks = []

    context_missing = not conversation_context
    if context_missing:
        fallbacks.append("context_missing")

    nodes, n_conf, n_fb = _find_matching_nodes_subset(
        all_facts, all_emotions, all_actions, index, label_set_index
    )
    confidence = n_conf
    fallbacks.extend(n_fb)
    if context_missing:
        confidence -= _cfg("confidence.context_missing_penalty", 0.1)

    if not nodes:
        return None

    if db is not None and nodes:
        pool = []
        for node in nodes:
            path_sig = node.get("path_signature", "") or node.get("state_id", "")
            node_row = await db.get_node_by_signature(path_sig)
            node_id = node_row["id"] if node_row else None
            if node_id:
                pool.extend(await db.get_sentences_by_node(node_id))
    else:
        pool = aggregate_pools(nodes)

    if not pool:
        d_pool, d_conf, d_fb = descend_for_sentences(nodes)
        fallbacks.extend(d_fb)
        if not d_pool:
            return None
        pool = d_pool

    for s in pool:
        s["_bitmask_score"] = compute_bitmask_score(s.get("bg_bitmask_int", 0), query_bitmask)

    ranked = await rank_sentences(pool, query_vec=query_vec, db=db,
                            query_bg=query_bg,
                            conversation_context=conversation_context,
                            context_missing=context_missing)

    if not ranked:
        return None

    top = ranked[0]
    confidence -= fallbacks.count("descend") * _cfg("confidence.descend_penalty", 0.05)
    top_bitmask_score = top.get("bitmask_score", 1.0)
    if top_bitmask_score < 1.0:
        confidence -= (1.0 - top_bitmask_score) * _cfg("confidence.bitmask_mismatch_penalty", 0.1)
    confidence = max(confidence, 0.0)

    return {
        "script_text": top.get("script_text", ""),
        "script_id": top.get("script_id", ""),
        "state_id": composite_state_id,
        "win_rate": top.get("win_rate", 0),
        "sas": top.get("sas", 0),
        "vec_score": top.get("vec_score", 0),
        "final_score": top.get("final_score", 0),
        "confidence": round(confidence, 2),
        "ranking_weights": get_ranking_weights(),
        "fallbacks": fallbacks,
        "conversation_state": path_state,
    }


if __name__ == "__main__":
    import asyncio

    async def _main():
        tree = _load_scored_tree()
        index = build_node_index(tree)
        _log.info(f"Index: {len(index)} keys, {sum(len(v) for v in index.values())} nodes")
        result = await recommend(
            query_bitmask=0,
            conversation_context="客户说没有钱",
            query_bg={},
            tree=tree, index=index,
        )
        if result:
            _log.info(f"Recommend: {result['script_id']} (confidence={result['confidence']}, final_score={result['final_score']:.4f})")
        else:
            _log.info("No recommendation")

    asyncio.run(_main())
