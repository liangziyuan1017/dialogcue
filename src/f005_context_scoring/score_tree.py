import importlib.util
import json
import os

from f005_context_scoring.scoring_metrics import (
    compute_bg_background,
    compute_bg_constraints,
    compute_hwr,
    compute_sas_for_pool,
    encode_bitmask,
    encode_bitmask_int,
)
from f007_infrastructure.config import get as _cfg
from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_texts
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)


def _load_py(filepath):
    spec = importlib.util.spec_from_file_location("mod", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_output_aligned():
    path = os.path.join(os.path.dirname(__file__), "..", "f001_schema_alignment", "data", "output_aligned.py")
    return _load_py(path).results


def _load_output_rewarded():
    path = os.path.join(os.path.dirname(__file__), "..", "f003_reward_labeling", "data", "output_rewarded.py")
    return _load_py(path).results


def _load_decision_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f004_decision_tree", "data", "decision_tree.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_state_keywords():
    path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "state_keywords.json")
    if not os.path.exists(path):
        return {}
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


def _extract_conversation_context(script_text, turns, window=None):
    if window is None:
        window = _cfg("context_window.conversation_turns", 20)
    if not turns:
        return ""
    script_prefix = script_text[:_cfg("context_window.script_prefix_length", 50)] if script_text else ""
    match_idx = -1
    if script_prefix:
        for i, t in enumerate(turns):
            text = t.get("text", "")
            if text.startswith(script_prefix) or script_prefix.startswith(text):
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
    for s, sas in zip(sentence_pool, sas_scores, strict=False):
        s["sas"] = sas
    if embed_fn is not None:
        texts = [s.get("conversation_context", "") or s.get("script_text", "") for s in sentence_pool]
        vecs = embed_fn(texts)
        for s, vec in zip(sentence_pool, vecs, strict=False):
            s["_context_vec"] = vec
    return sentence_pool


def score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup=None, embed_fn=None):
    def _walk(node, parent_path=""):
        state_id = node.get("state_id", "")
        path_sig = f"{parent_path}/{state_id}" if parent_path else state_id
        node["path_signature"] = path_sig
        _score_sentence_pool(
            node.get("sentence_pool", []),
            context_lookup,
            reward_lookup,
            customer_info_lookup,
            conv_ctx_lookup,
            embed_fn=embed_fn,
        )
        for child in node.get("children", []):
            _walk(child, parent_path=path_sig)

    _walk(tree)
    return tree


def _collect_tree_nodes(tree, parent_id_map=None):
    if parent_id_map is None:
        parent_id_map = {}
    nodes = []
    def walk(node, parent_path="", depth=0):
        state_id = node.get("state_id", "")
        path_sig = f"{parent_path}/{state_id}" if parent_path else state_id
        nodes.append({
            "state_id": state_id,
            "path_signature": path_sig,
            "branch_key": node.get("branch_key", {}),
            "parent_id": parent_id_map.get(parent_path) if parent_path else None,
            "depth": depth,
        })
        for child in node.get("children", []):
            walk(child, parent_path=path_sig, depth=depth + 1)
    walk(tree)
    return nodes


def _collect_tree_sentences(tree):
    sentences = []
    def walk(node, parent_path=""):
        state_id = node.get("state_id", "")
        path_sig = f"{parent_path}/{state_id}" if parent_path else state_id
        for s in node.get("sentence_pool", []):
            s["_node_path_sig"] = path_sig
            sentences.append(s)
        for child in node.get("children", []):
            walk(child, parent_path=path_sig)
    walk(tree)
    return sentences


def write_scored_tree(output_path=None, db=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "decision_tree_scored.json")
    tree = _load_decision_tree()
    context_lookup = build_context_lookup()
    reward_lookup = build_reward_lookup()
    customer_info_lookup = build_customer_info_lookup()
    turns_lookup = build_turns_lookup()
    conv_ctx_lookup = build_conversation_context_lookup(tree, turns_lookup)
    scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup, embed_fn=embed_texts if db is not None else None)

    all_sentences = _collect_tree_sentences(scored)
    for s in all_sentences:
        s["context_vec_id"] = s.get("script_id", "")

    if db is not None:
        all_nodes = _collect_tree_nodes(scored)
        db.upsert_nodes(all_nodes)
        node_sig_to_id = {}
        for n in all_nodes:
            row = db.get_node_by_signature(n["path_signature"])
            if row:
                node_sig_to_id[n["path_signature"]] = row["id"]
        db_sentences = []
        for s in all_sentences:
            node_sig = s.get("_node_path_sig", "")
            node_id = node_sig_to_id.get(node_sig, 1)
            db_sentences.append({
                "script_id": s.get("script_id", ""),
                "node_id": node_id,
                "script_text": s.get("script_text", ""),
                "bg_bitmask_int": s.get("bg_bitmask_int", 0),
                "win_rate": s.get("win_rate", 0),
                "sas": s.get("sas", 0),
                "bg_background": s.get("bg_background"),
                "conversation_context": s.get("conversation_context", ""),
                "embedding": s.get("_context_vec") or [0.0] * EMBEDDING_DIM,
            })
        db.upsert_sentences(db_sentences)

        keywords = _load_state_keywords()
        if keywords:
            kw_rows = []
            for category in ["facts", "emotions", "collector_actions"]:
                for group in keywords.get(category, []):
                    for kw in group.get("keywords", []):
                        kw_rows.append({
                            "group_name": group.get("group_name") or "",
                            "category": category,
                            "keyword": kw,
                            "frequency": group.get("frequency", 0),
                        })
            if kw_rows:
                cur = db._conn.cursor()
                for kr in kw_rows:
                    cur.execute(
                        "INSERT INTO taxonomy_keywords (group_name, category, keyword, frequency) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (kr["group_name"], kr["category"], kr["keyword"], kr["frequency"]),
                    )
                cur.close()

    for s in all_sentences:
        s.pop("_context_vec", None)
        s.pop("_node_path_sig", None)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    return scored


if __name__ == "__main__":
    scored = write_scored_tree()
    _log.info("Wrote scored tree to decision_tree_scored.json")
