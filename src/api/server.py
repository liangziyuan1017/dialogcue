import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel
import socketio

from f006_retrieval_engine.retrieval_engine import (
    build_node_index,
    recommend,
    _compute_keyword_freq,
)
from f006_retrieval_engine.state_extraction import extract_state, merge_state
from infra.embeddings import embed_single
from infra.db import SentenceDB


class ConversationState(BaseModel):
    facts: list[str]
    emotions: list[str]
    actions: list[str]
    willingness: str | None = None


class RecommendRequest(BaseModel):
    customer_utterance: str
    conversation_context: str = ""
    conversation_state: ConversationState
    context: dict


def _init_db():
    dsn = os.environ.get("PG_DSN", "dbname=icbc user=postgres")
    db = SentenceDB(dsn)
    db.create_tables()
    return db


def _init_taxonomy():
    path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "state_keywords.json")
    if not os.path.exists(path):
        return {"facts": [], "emotions": [], "collector_actions": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _init_hash_index(db):
    cur = db._conn.cursor()
    cur.execute("SELECT path_signature, id FROM nodes")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: r[1] for r in rows}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = _init_db()
    app.state.taxonomy = _init_taxonomy()
    app.state.hash_index = _init_hash_index(app.state.db)
    tree = _load_scored_tree()
    app.state.tree = tree
    app.state.index = build_node_index(tree)
    app.state.keyword_freq = _compute_keyword_freq(app.state.index)
    yield


def _load_scored_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "decision_tree_scored.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


app = FastAPI(lifespan=lifespan)
sio = socketio.Server(async_mode="threading")
sessions = {}


@app.post("/recommend")
async def recommend_endpoint(req: RecommendRequest):
    start = time.time()

    extraction = extract_state(req.customer_utterance, app.state.taxonomy, db=app.state.db)
    merged = merge_state(
        {"facts": req.conversation_state.facts, "emotions": req.conversation_state.emotions, "actions": req.conversation_state.actions},
        extraction,
    )

    facts = merged["facts"]
    emotions = merged["emotions"]
    branch_key_values = emotions + merged["actions"]

    query_bitmask = _compute_bitmask(req.context)
    embed_fallback = False
    if req.conversation_context:
        try:
            query_vec = embed_single(req.conversation_context)
        except Exception:
            query_vec = [0.0] * 768
            embed_fallback = True
    else:
        query_vec = [0.0] * 768

    result = recommend(
        inherited_facts=facts,
        branch_key_values=branch_key_values,
        query_bitmask=query_bitmask,
        conversation_context=req.conversation_context,
        query_bg=req.context,
        tree=app.state.tree,
        index=app.state.index,
        keyword_freq=app.state.keyword_freq,
        db=app.state.db,
        query_vec=query_vec,
        conversation_state=merged,
    )

    latency_ms = int((time.time() - start) * 1000)

    if result is None:
        return {"error": "no recommendation found", "latency_ms": latency_ms}

    if embed_fallback:
        result["confidence"] = max(result.get("confidence", 1.0) - 0.1, 0.0)
        result.setdefault("fallbacks", [])
        if "embed_fail" not in result["fallbacks"]:
            result["fallbacks"].append("embed_fail")

    from f006_retrieval_engine.retrieval_ranking import RANKING_WEIGHTS
    return {
        "script_text": result.get("script_text", ""),
        "script_id": result.get("script_id", ""),
        "state_id": result.get("state_id", ""),
        "win_rate": result.get("win_rate", 0),
        "vec_score": result.get("vec_score", 0),
        "sas": result.get("sas", 0),
        "final_score": result.get("final_score", 0),
        "confidence": result.get("confidence", 1.0),
        "extraction_method": extraction.get("method", "unknown"),
        "conversation_state": merged,
        "ranking_weights": RANKING_WEIGHTS,
        "fallbacks": result.get("fallbacks", []),
        "latency_ms": latency_ms,
    }


def _compute_bitmask(context: dict) -> int:
    from f006_retrieval_engine.retrieval_ranking import BITMASK_FIELDS
    mask = 0
    for i, field in enumerate(BITMASK_FIELDS):
        if context.get(field, False):
            mask |= (1 << i)
    return mask


@sio.on("start_session")
def start_session(sid, data):
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    sessions[session_id] = {
        "cust_no": data.get("cust_no", ""),
        "context": data.get("context", {}),
        "conversation_state": {"facts": [], "emotions": [], "actions": []},
        "conversation_context_buffer": "",
        "transcript": [],
        "start_time": datetime.now(),
    }
    return {"session_id": session_id, "conversation_state": sessions[session_id]["conversation_state"]}


@sio.on("customer_turn")
def customer_turn(sid, data):
    session_id = data.get("session_id", "")
    session = sessions.get(session_id)
    if not session:
        return {"error": "session not found"}

    utterance = data.get("utterance", "")
    conv_ctx = data.get("conversation_context", "")

    start = time.time()
    extraction = extract_state(utterance, app.state.taxonomy, db=app.state.db)
    merged = merge_state(session["conversation_state"], extraction)
    session["conversation_state"] = merged

    signature = "|".join(sorted(merged["facts"] + merged["emotions"] + merged["actions"]))
    node_id = app.state.hash_index.get(signature, 1)
    query_bitmask = _compute_bitmask(session["context"])
    try:
        query_vec = embed_single(conv_ctx) if conv_ctx else [0.0] * 768
    except Exception:
        query_vec = [0.0] * 768

    candidates = app.state.db.search_similar(query_vec, node_id=node_id, query_bitmask=query_bitmask, limit=50)
    from f006_retrieval_engine.retrieval_ranking import rank_sentences, RANKING_WEIGHTS
    ranked = rank_sentences(candidates, query_vec=query_vec, db=app.state.db, query_bg=session["context"])

    latency_ms = int((time.time() - start) * 1000)
    top = ranked[0] if ranked else {}

    entry = {"turn": len(session["transcript"]) + 1, "role": "customer", "utterance": utterance}
    if top:
        entry["recommendation"] = {
            "script_text": top.get("script_text", ""),
            "script_id": top.get("script_id", ""),
            "final_score": top.get("final_score", 0),
        }
    session["transcript"].append(entry)
    session["conversation_context_buffer"] += " " + utterance

    result = {
        "script_text": top.get("script_text", ""),
        "script_id": top.get("script_id", ""),
        "state_id": signature,
        "win_rate": top.get("win_rate", 0),
        "vec_score": top.get("vec_score", 0),
        "sas": top.get("sas", 0),
        "final_score": top.get("final_score", 0),
        "confidence": top.get("confidence", 1.0),
        "extraction_method": extraction.get("method", "unknown"),
        "conversation_state": merged,
        "ranking_weights": RANKING_WEIGHTS,
        "fallbacks": [],
        "latency_ms": latency_ms,
    }

    sio.emit("recommendation", {"session_id": session_id, **result}, room=sid)
    return result


@sio.on("collector_turn")
def collector_turn(sid, data):
    session_id = data.get("session_id", "")
    session = sessions.get(session_id)
    if not session:
        return {"error": "session not found"}

    utterance = data.get("utterance", "")
    extraction = extract_state(utterance, app.state.taxonomy, db=app.state.db)
    new_actions = extraction.get("actions", [])
    merged = merge_state(session["conversation_state"], {"facts": [], "emotions": [], "actions": new_actions})
    session["conversation_state"] = merged

    session["transcript"].append({
        "turn": len(session["transcript"]) + 1,
        "role": "collector",
        "utterance": utterance,
        "extracted_actions": new_actions,
    })

    return {"recorded": True, "extracted_actions": new_actions, "conversation_state": merged}


@sio.on("end_session")
def end_session(sid, data):
    session_id = data.get("session_id", "")
    session = sessions.pop(session_id, None)
    if not session:
        return {"error": "session not found"}

    duration = (datetime.now() - session["start_time"]).total_seconds()
    return {
        "session_id": session_id,
        "duration_seconds": int(duration),
        "turn_count": len(session["transcript"]),
        "final_conversation_state": session["conversation_state"],
        "transcript": session["transcript"],
    }


app.mount("/socket.io", socketio.WSGIApp(sio))
