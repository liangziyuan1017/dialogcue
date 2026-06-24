import importlib.util
import json
import os

from f005_context_scoring.scoring_metrics import (
    BITMASK_FIELDS,
    BG_BACKGROUND_FIELDS,
    _extract_bg_constraints,
    _extract_bg_background,
    compute_bg_background,
    compute_bg_constraints,
    compute_hwr,
    compute_sas_for_pool,
    cosine_similarity,
    encode_bitmask,
    encode_bitmask_int,
)


def _load_py(filepath):
    spec = importlib.util.spec_from_file_location("mod", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_output_aligned():
    path = os.path.join(os.path.dirname(__file__), "..", "f001_schema_alignment", "output_aligned.py")
    return _load_py(path).results


def _load_output_rewarded():
    path = os.path.join(os.path.dirname(__file__), "..", "f003_reward_labeling", "output_rewarded.py")
    return _load_py(path).results


def _load_decision_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f004_decision_tree", "decision_tree.json")
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


def build_turns_lookup(records=None):
    if records is None:
        records = _load_output_aligned()
    return {r["call_id"]: r.get("turns_annotated", []) for r in records}


def _extract_conversation_context(script_text, turns, window=20):
    if not turns:
        return ""
    script_prefix = script_text[:30] if script_text else ""
    match_idx = -1
    for i, t in enumerate(turns):
        text = t.get("text", "")
        if script_prefix and text.startswith(script_prefix):
            match_idx = i
            break
    if match_idx == -1:
        match_idx = len(turns)
    start = max(0, match_idx - window)
    context_turns = turns[start:match_idx]
    return " ".join(t.get("text", "") for t in context_turns)


def build_conversation_context_lookup(tree, turns_lookup=None):
    if turns_lookup is None:
        turns_lookup = build_turns_lookup()
    context_map = {}
    def walk(node):
        for s in node.get("sentence_pool", []):
            call_ids = s.get("source_call_ids", [])
            contexts = []
            for cid in call_ids:
                turns = turns_lookup.get(cid, [])
                ctx = _extract_conversation_context(s.get("script_text", ""), turns)
                if ctx:
                    contexts.append(ctx)
            context_map[s.get("script_id", "")] = contexts[0] if contexts else ""
        for child in node.get("children", []):
            walk(child)
    walk(tree)
    return context_map


def _score_sentence_pool(sentence_pool, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup=None, embed_fn=None):
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
        if conv_ctx_lookup is not None:
            s["conversation_context"] = conv_ctx_lookup.get(s.get("script_id", ""), "")
    sas_scores = compute_sas_for_pool(sentence_pool)
    for s, sas in zip(sentence_pool, sas_scores):
        s["sas"] = sas
    if embed_fn is not None:
        texts = [s.get("script_text", "") for s in sentence_pool]
        vecs = embed_fn(texts)
        for s, vec in zip(sentence_pool, vecs):
            s["_context_vec"] = vec
    return sentence_pool


def score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup=None, embed_fn=None):
    def _walk(node):
        _score_sentence_pool(
            node.get("sentence_pool", []),
            context_lookup,
            reward_lookup,
            customer_info_lookup,
            conv_ctx_lookup,
            embed_fn=embed_fn,
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
    turns_lookup = build_turns_lookup()
    conv_ctx_lookup = build_conversation_context_lookup(tree, turns_lookup)
    scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    return scored


if __name__ == "__main__":
    scored = write_scored_tree()
    print(f"Wrote scored tree to decision_tree_scored.json")
