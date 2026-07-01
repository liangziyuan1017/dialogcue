import time

from f008_state_extraction.state_extraction import extract_state, merge_state
from f007_infrastructure.embeddings import embed_single, EMBEDDING_DIM
from f006_retrieval_engine.retrieval_engine import (
    recommend,
    compute_bitmask_score,
    _find_matching_nodes_subset,
    aggregate_pools,
    descend_for_sentences,
    _build_label_set_index,
)
from f006_retrieval_engine.retrieval_ranking import BITMASK_FIELDS, rank_sentences
from f007_infrastructure.config import get as _cfg


def _compute_bitmask(context: dict) -> int:
    mask = 0
    for i, field in enumerate(BITMASK_FIELDS):
        if context.get(field, False):
            mask |= (1 << i)
    return mask


def _get_all_candidates(query_bitmask, conversation_context, query_bg,
                        tree, index, label_set_index, db, query_vec,
                        conversation_state):
    from f008_state_extraction.state_extraction import path_state_to_flat, flat_to_path_state

    if conversation_state is None:
        conversation_state = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}

    if "branch_key" in conversation_state:
        all_facts, all_emotions, all_actions = path_state_to_flat(conversation_state)
    else:
        all_facts = conversation_state.get("facts", [])
        all_emotions = conversation_state.get("emotions", [])
        all_actions = conversation_state.get("actions", [])

    fallbacks = []
    context_missing = not conversation_context
    if context_missing:
        fallbacks.append("context_missing")

    nodes, n_conf, n_fb = _find_matching_nodes_subset(
        all_facts, all_emotions, all_actions, index, label_set_index
    )
    if not nodes:
        return []

    if db is not None and nodes:
        pool = []
        for node in nodes:
            path_sig = node.get("path_signature", "") or node.get("state_id", "")
            node_row = db.get_node_by_signature(path_sig)
            node_id = node_row["id"] if node_row else None
            if node_id:
                pool.extend(db.get_sentences_by_node(node_id))
    else:
        pool = aggregate_pools(nodes)

    if not pool:
        d_pool, d_conf, d_fb = descend_for_sentences(nodes)
        if not d_pool:
            return []
        pool = d_pool

    for s in pool:
        s["_bitmask_score"] = compute_bitmask_score(s.get("bg_bitmask_int", 0), query_bitmask)

    ranked = rank_sentences(pool, query_vec=query_vec, db=db,
                            query_bg=query_bg,
                            conversation_context=conversation_context,
                            context_missing=context_missing)
    return ranked or []


def debug_recommend(req: dict, app_state) -> dict:
    trace = []
    customer_utterance = req.get("customer_utterance", "")
    conversation_context = req.get("conversation_context", "")
    conversation_state = req.get("conversation_state", {})
    context = req.get("context", {})

    t0 = time.time()
    extraction = extract_state(customer_utterance, app_state.taxonomy, db=app_state.db)
    trace.append({
        "step": "extract_state",
        "input": {"customer_utterance": customer_utterance},
        "output": extraction,
        "latency_ms": int((time.time() - t0) * 1000),
    })

    t0 = time.time()
    merged = merge_state(conversation_state, extraction)
    trace.append({
        "step": "merge_state",
        "input": {"conversation_state": conversation_state, "extraction": extraction},
        "output": merged,
        "latency_ms": int((time.time() - t0) * 1000),
    })

    t0 = time.time()
    query_bitmask = _compute_bitmask(context)
    trace.append({
        "step": "compute_bitmask",
        "input": {"context": context},
        "output": {"bitmask": query_bitmask},
        "latency_ms": int((time.time() - t0) * 1000),
    })

    t0 = time.time()
    try:
        query_vec = embed_single(conversation_context) if conversation_context else [0.0] * EMBEDDING_DIM
        embed_fallback = False
    except Exception:
        query_vec = [0.0] * EMBEDDING_DIM
        embed_fallback = True
    trace.append({
        "step": "embed",
        "input": {"conversation_context": conversation_context},
        "output": {"dim": len(query_vec), "fallback": embed_fallback},
        "latency_ms": int((time.time() - t0) * 1000),
    })

    t0 = time.time()
    rec_result = recommend(
        query_bitmask=query_bitmask,
        conversation_context=conversation_context,
        query_bg=context,
        tree=app_state.tree,
        index=app_state.index,
        label_set_index=app_state.label_set_index,
        db=app_state.db,
        query_vec=query_vec,
        conversation_state=merged,
    )
    trace.append({
        "step": "recommend",
        "input": {"bitmask": query_bitmask, "conversation_context": conversation_context},
        "output": rec_result,
        "latency_ms": int((time.time() - t0) * 1000),
    })

    t0 = time.time()
    all_ranked = _get_all_candidates(
        query_bitmask=query_bitmask,
        conversation_context=conversation_context,
        query_bg=context,
        tree=app_state.tree,
        index=app_state.index,
        label_set_index=app_state.label_set_index,
        db=app_state.db,
        query_vec=query_vec,
        conversation_state=merged,
    )
    trace.append({
        "step": "rank_all_candidates",
        "input": {"bitmask": query_bitmask},
        "output": {"count": len(all_ranked)},
        "latency_ms": int((time.time() - t0) * 1000),
    })

    recommendation = None
    if rec_result is not None:
        recommendation = {
            "script_text": rec_result.get("script_text", ""),
            "script_id": rec_result.get("script_id", ""),
            "state_id": rec_result.get("state_id", ""),
            "win_rate": rec_result.get("win_rate", 0),
            "vec_score": rec_result.get("vec_score", 0),
            "sas": rec_result.get("sas", 0),
            "bitmask_score": rec_result.get("bitmask_score", 1.0),
            "final_score": rec_result.get("final_score", 0),
            "confidence": rec_result.get("confidence", 1.0),
            "fallbacks": rec_result.get("fallbacks", []),
        }

    candidates = []
    for c in all_ranked[:20]:
        candidates.append({
            "script_text": c.get("script_text", ""),
            "script_id": c.get("script_id", ""),
            "win_rate": c.get("win_rate", 0),
            "sas": c.get("sas", 0),
            "vec_score": c.get("vec_score", 0),
            "bitmask_score": c.get("bitmask_score", 1.0),
            "final_score": c.get("final_score", 0),
        })

    return {
        "trace": trace,
        "recommendation": recommendation,
        "candidates": candidates,
    }
