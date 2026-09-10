import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.logging import bind_request_id, reset_request_id
from f007_infrastructure.logging import get_logger as _get_logger

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import socketio
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

_log = _get_logger(__name__)

from f006_retrieval_engine.retrieval_engine import (
    _build_label_set_index,
    build_node_index,
    recommend,
)
from f006_retrieval_engine.retrieval_ranking import BITMASK_FIELDS, get_ranking_weights
from f007_infrastructure.async_db import AsyncSentenceDB
from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_single
from f008_state_extraction.state_extraction import extract_state, merge_state
from f009_api_server.rate_limit import RateLimiter
from f009_api_server.session_store import SessionStore
from f009_api_server.tag_mapping import map_cust_tags_to_context

_REQUEST_MAX_CHARS = _cfg("server.request_max_chars", 8000)

_EMBED_CONTEXT_MAX_WORDS = 100


def _last_n_words(text: str, n: int = _EMBED_CONTEXT_MAX_WORDS) -> str:
    words = text.split()
    return " ".join(words[-n:]) if words else ""


class ConversationState(BaseModel):
    branch_key: dict = {}
    inherited_facts: list[str] = []
    inherited_emotions: list[str] = []
    willingness: str | None = None


class RecommendRequest(BaseModel):
    customer_utterance: str = Field(max_length=_REQUEST_MAX_CHARS)
    conversation_context: str = Field(default="", max_length=_REQUEST_MAX_CHARS)
    conversation_state: ConversationState
    context: dict


class StartSessionIn(BaseModel):
    cust_no: str = ""
    context: dict = {}


class CustomerTurnIn(BaseModel):
    session_id: str
    utterance: str = Field(max_length=_REQUEST_MAX_CHARS)
    conversation_context: str = Field(default="", max_length=_REQUEST_MAX_CHARS)


class CollectorTurnIn(BaseModel):
    session_id: str
    utterance: str = Field(max_length=_REQUEST_MAX_CHARS)


class CustTag(BaseModel):
    tag: str = ""
    value: str = ""


class ExternalCustomer(BaseModel):
    cust_no: str = ""
    ac_no: str = ""
    called_no: str = ""


class ExternalSessionStartRequest(BaseModel):
    call_id: str = Field(max_length=_REQUEST_MAX_CHARS)
    call_info: dict = {}
    agent: dict = {}
    customer: ExternalCustomer = ExternalCustomer()
    cust_tags: list[CustTag] = Field(default=[], max_length=500)


_EXTERNAL_HISTORY_ITEM = Annotated[str, StringConstraints(max_length=_REQUEST_MAX_CHARS)]


class ExternalRecommendRequest(BaseModel):
    call_id: str = Field(max_length=_REQUEST_MAX_CHARS)
    current_text: str = Field(max_length=_REQUEST_MAX_CHARS)
    history_context: list[_EXTERNAL_HISTORY_ITEM] = Field(default=[], max_length=100)


def _validate_start_session(data: dict) -> StartSessionIn:
    return StartSessionIn(**data)


def _validate_customer_turn(data: dict) -> CustomerTurnIn:
    return CustomerTurnIn(**data)


def _validate_collector_turn(data: dict) -> CollectorTurnIn:
    return CollectorTurnIn(**data)


def _init_db():
    dsn = os.environ.get("PG_DSN", "dbname=icbc user=postgres")
    if "://" not in dsn:
        parts = {}
        for token in dsn.split():
            if "=" in token:
                k, v = token.split("=", 1)
                parts[k] = v
        host = parts.get("host", "localhost")
        port = parts.get("port", "5432")
        dbname = parts.get("dbname", "icbc")
        # Match libpq: omit user → OS username (not hard-coded "postgres")
        import getpass
        user = parts.get("user") or getpass.getuser()
        password = parts.get("password", "")
        cred = f"{user}:{password}" if password else user
        dsn = f"postgresql://{cred}@{host}:{port}/{dbname}"
    return AsyncSentenceDB(dsn)


def _init_taxonomy():
    path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "state_keywords.json")
    if not os.path.exists(path):
        return {"facts": [], "emotions": [], "collector_actions": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _check_api_key_guard():
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key.startswith("sk-placeholder"):
        return False, "DEEPSEEK_API_KEY is placeholder; provide a real key in .env"
    return True, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    for legacy_name in ("tree", "index", "label_set_index"):
        app.state._state.pop(legacy_name, None)
    ready, reason = _check_api_key_guard()
    app.state.ready = ready
    app.state.ready_reason = reason
    app.state.boot_errors = []
    if not ready:
        app.state.boot_errors.append(reason or "api key guard failed")
        _log.warning("startup guard: %s", reason)
        yield
        return
    app.state.db = _init_db()
    await app.state.db.connect()
    await app.state.db.create_tables()
    try:
        app.state.taxonomy = _init_taxonomy()
    except Exception as e:
        app.state.boot_errors.append(f"taxonomy: {e}")
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        _log.error("taxonomy load failed: %s", e)
    app.state.ready = not app.state.boot_errors
    yield
    if hasattr(app.state, "db") and app.state.db is not None:
        await app.state.db.close()


def _load_scored_tree():
    path = os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "data", "decision_tree_scored.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg("server.allowed_origins", ["*"]),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
sio = socketio.AsyncServer(async_mode="asgi")
sessions = SessionStore(
    max_sessions=_cfg("server.session_max", 10000),
    ttl=_cfg("server.session_ttl", 7200),
)

_rate_limiter = RateLimiter(
    rate_rps=_cfg("server.rate_limit_rps", 20),
    burst=_cfg("server.rate_limit_burst", 40),
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    inbound = request.headers.get("X-Request-ID")
    rid = inbound or f"req_{uuid.uuid4().hex[:12]}"
    reset = bind_request_id(rid)
    try:
        if request.url.path in ("/recommend", "/api/v1/recommend") and not _rate_limiter.allow(request.client.host if request.client else "anonymous"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"error": "rate limit exceeded"}, headers={"X-Request-ID": rid})
        response = await call_next(request)
    finally:
        reset_request_id(reset)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/health")
async def health():
    return {"status": "up"}


@app.get("/readyz")
async def readyz():
    ready = getattr(app.state, "ready", False)
    errors = getattr(app.state, "boot_errors", [])
    if ready and hasattr(app.state, "db") and app.state.db is not None:
        try:
            await app.state.db.ping()
        except Exception as e:
            ready = False
            errors = errors + [f"db ping: {e}"]
    if ready:
        return {"ready": True}
    return JSONResponse(status_code=503, content={"ready": False, "errors": errors})


@app.post("/admin/reload-taxonomy")
async def reload_taxonomy():
    try:
        fresh = await app.state.db.load_taxonomy_from_db()
        app.state.taxonomy = fresh
        from f008_state_extraction.state_extraction import invalidate_extract_cache
        invalidate_extract_cache()
        return {"reloaded": True, "facts": len(fresh.get("facts", [])), "emotions": len(fresh.get("emotions", []))}
    except Exception as e:
        return JSONResponse(status_code=503, content={"reloaded": False, "error": str(e)})


@app.post("/recommend")
async def recommend_endpoint(req: RecommendRequest):
    if not getattr(app.state, "ready", False):
        return JSONResponse(status_code=503, content={"error": "service not ready", "reason": getattr(app.state, "ready_reason", None) or "; ".join(getattr(app.state, "boot_errors", []))})
    start = time.time()

    extraction = await extract_state(req.customer_utterance, app.state.taxonomy, db=app.state.db)
    merged = merge_state(
        {
            "branch_key": req.conversation_state.branch_key,
            "inherited_facts": req.conversation_state.inherited_facts,
            "inherited_emotions": req.conversation_state.inherited_emotions,
            "willingness": req.conversation_state.willingness,
        },
        extraction,
    )

    query_bitmask = _compute_bitmask(req.context)
    embed_fallback = False
    if req.conversation_context:
        try:
            query_vec = embed_single(_last_n_words(req.conversation_context))
        except Exception:
            query_vec = [0.0] * EMBEDDING_DIM
            embed_fallback = True
    else:
        query_vec = [0.0] * EMBEDDING_DIM

    result = await recommend(
        query_bitmask=query_bitmask,
        conversation_context=req.conversation_context,
        query_bg=req.context,
        db=app.state.db,
        query_vec=query_vec,
        conversation_state=merged,
    )

    latency_ms = int((time.time() - start) * 1000)

    if result is None:
        return {"error": "no recommendation found", "latency_ms": latency_ms}

    if embed_fallback:
        result["confidence"] = max(result.get("confidence", 1.0) - _cfg("confidence.embed_fallback_penalty", 0.1), 0.0)
        result.setdefault("fallbacks", [])
        if "embed_fail" not in result["fallbacks"]:
            result["fallbacks"].append("embed_fail")

    return {
        "script_text": result.get("script_text", ""),
        "script_id": result.get("script_id", ""),
        "state_id": result.get("state_id", ""),
        "win_rate": result.get("win_rate", 0),
        "vec_score": result.get("vec_score", 0),
        "sas": result.get("sas", 0),
        "bitmask_score": result.get("bitmask_score", 1.0),
        "final_score": result.get("final_score", 0),
        "confidence": result.get("confidence", 1.0),
        "extraction_method": extraction.get("method", "unknown"),
        "conversation_state": merged,
        "ranking_weights": get_ranking_weights(),
        "fallbacks": result.get("fallbacks", []),
        "latency_ms": latency_ms,
    }


def _compute_bitmask(context: dict) -> int:
    mask = 0
    for i, field in enumerate(BITMASK_FIELDS):
        if context.get(field, False):
            mask |= (1 << i)
    return mask


def _not_ready_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "service not ready",
            "reason": getattr(app.state, "ready_reason", None) or "; ".join(getattr(app.state, "boot_errors", [])),
        },
    )


@app.post("/api/v1/session/start")
async def external_session_start(req: ExternalSessionStartRequest):
    if not getattr(app.state, "ready", False):
        return _not_ready_response()
    context = map_cust_tags_to_context(
        [{"tag": t.tag, "value": t.value} for t in req.cust_tags]
    )
    session_id = await _create_session(
        req.customer.cust_no, context, session_id=req.call_id,
        call_info=req.call_info, agent=req.agent,
    )
    return {"call_id": session_id}


@app.post("/api/v1/recommend")
async def external_recommend(req: ExternalRecommendRequest):
    if not getattr(app.state, "ready", False):
        return _not_ready_response()
    conv_ctx = " ".join(req.history_context + [req.current_text])
    result = await _run_turn(req.call_id, req.current_text, conv_ctx)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "session not found", "call_id": req.call_id})
    turn = result["entry"]["turn"]
    rec_id = f"rec_{req.call_id}_{turn:03d}"
    state_tags = result["extraction"].get("facts", []) + result["extraction"].get("emotions", [])
    rec_result = result["rec_result"]
    recommendation = rec_result.get("script_text") if rec_result else None
    confidence = rec_result.get("confidence", 0.0) if rec_result else 0.0
    return {
        "recommendation": recommendation,
        "state_tags": state_tags,
        "confidence": confidence,
        "rec_id": rec_id,
        "info": "",
    }


@app.delete("/api/v1/session/end")
async def external_session_end(call_id: str = Query(...)):
    if not getattr(app.state, "ready", False):
        return _not_ready_response()
    session = _end_session(call_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": "session not found", "call_id": call_id})
    return {"code": 0, "message": "session closed", "call_id": call_id}


def _get_db():
    return getattr(app.state, "db", None)


async def _persist_session(session_id: str, session: dict) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        await db.save_session(
            session_id, session["cust_no"], session["context"], session["conversation_state"],
            call_info=session.get("call_info"), agent=session.get("agent"),
        )
    except Exception:
        _log.warning("failed to persist session %s", session_id, exc_info=True)


async def _create_session(
    cust_no: str,
    context: dict,
    session_id: str | None = None,
    call_info: dict | None = None,
    agent: dict | None = None,
) -> str:
    """Create session in SessionStore + persist to DB.

    If session_id is None, auto-generate (SocketIO behavior).
    call_info and agent are stored on the session for external API context.
    Returns session_id.
    """
    if session_id is None:
        session_id = sessions.create(cust_no, context)
    else:
        session_id = sessions.create_with_id(session_id, cust_no, context)
    if session_id is None:
        raise RuntimeError("failed to create session")
    session = sessions.get(session_id)
    if session is not None:
        if call_info is not None:
            session["call_info"] = call_info
        if agent is not None:
            session["agent"] = agent
        await _persist_session(session_id, session)
    return session_id


def _end_session(session_id: str) -> dict | None:
    """Remove session from SessionStore. Returns session dict or None."""
    return sessions.remove(session_id)


@sio.on("start_session")
async def start_session(sid, data):
    try:
        payload = _validate_start_session(data or {})
    except ValueError as e:
        return {"error": "invalid payload", "detail": str(e)}
    session_id = await _create_session(payload.cust_no, payload.context)
    return {"session_id": session_id, "conversation_state": sessions.get(session_id)["conversation_state"]}


@sio.on("resume_session")
async def resume_session(sid, data):
    session_id = (data or {}).get("session_id", "")
    if not session_id:
        return {"error": "session_id required"}
    existing = sessions.get(session_id)
    if existing is not None:
        return {"session_id": session_id, "conversation_state": existing["conversation_state"], "transcript": existing["transcript"], "recovered": False}
    db = _get_db()
    if db is None:
        return {"error": "session not found and db unavailable"}
    try:
        row = await db.load_session(session_id)
        if row is None:
            return {"error": "session not found"}
        turns = await db.load_transcript_turns(session_id)
        start_time = row.get("start_time", datetime.now())
        if hasattr(start_time, "tzinfo") and start_time.tzinfo is not None:
            start_time = start_time.astimezone().replace(tzinfo=None)
        session = {
            "cust_no": row.get("cust_no", ""),
            "context": row.get("context", {}),
            "conversation_state": row.get("conversation_state", {}),
            "conversation_context_buffer": "".join(f" {t['utterance']}" for t in turns),
            "transcript": turns,
            "start_time": start_time,
            "call_info": row.get("call_info") or {},
            "agent": row.get("agent") or {},
        }
        sessions.restore(session_id, session)
        return {"session_id": session_id, "conversation_state": session["conversation_state"], "transcript": session["transcript"], "recovered": True}
    except Exception as e:
        _log.warning("failed to resume session %s", session_id, exc_info=True)
        return {"error": "recovery failed", "detail": str(e)}


async def _run_turn(session_id: str, utterance: str, conv_ctx: str) -> dict | None:
    """Core recommendation logic shared by SocketIO customer_turn and external REST /api/v1/recommend.

    Returns dict with: extraction, merged, rec_result, latency_ms, entry
    or None if session not found.
    """
    session = sessions.get(session_id)
    if not session:
        return None

    async with sessions.lock(session_id):
        start = time.time()
        extraction = await extract_state(utterance, app.state.taxonomy, db=app.state.db)
        merged = merge_state(session["conversation_state"], extraction)
        session["conversation_state"] = merged

        query_bitmask = _compute_bitmask(session["context"])
        try:
            query_vec = embed_single(_last_n_words(conv_ctx)) if conv_ctx else [0.0] * EMBEDDING_DIM
        except Exception:
            query_vec = [0.0] * EMBEDDING_DIM

        rec_result = await recommend(
            query_bitmask=query_bitmask,
            conversation_context=conv_ctx,
            query_bg=session["context"],
            db=app.state.db,
            query_vec=query_vec,
            conversation_state=merged,
        )

        latency_ms = int((time.time() - start) * 1000)

        top = rec_result if rec_result is not None else {}

        entry = {"turn": len(session["transcript"]) + 1, "role": "customer", "utterance": utterance}
        if top:
            entry["recommendation"] = {
                "script_text": top.get("script_text", ""),
                "script_id": top.get("script_id", ""),
                "final_score": top.get("final_score", 0),
            }
        session["transcript"].append(entry)
        session["conversation_context_buffer"] += " " + utterance

        db = _get_db()
        if db is not None:
            try:
                extra = {"recommendation": entry["recommendation"]} if "recommendation" in entry else {}
                await db.append_transcript_turn(session_id, entry["turn"], "customer", utterance, extra)
                await db.save_session(session_id, session["cust_no"], session["context"], session["conversation_state"], call_info=session.get("call_info"), agent=session.get("agent"))
            except Exception:
                _log.warning("failed to persist turn for session %s", session_id, exc_info=True)

    return {
        "extraction": extraction,
        "merged": merged,
        "rec_result": rec_result,
        "latency_ms": latency_ms,
        "entry": entry,
    }


@sio.on("customer_turn")
async def customer_turn(sid, data):
    try:
        payload = _validate_customer_turn(data or {})
    except ValueError as e:
        return {"error": "invalid payload", "detail": str(e)}
    session_id = payload.session_id

    result = await _run_turn(session_id, payload.utterance, payload.conversation_context)
    if result is None:
        return {"error": "session not found"}

    top = result["rec_result"] if result["rec_result"] is not None else {}
    response = {
        "script_text": top.get("script_text", ""),
        "script_id": top.get("script_id", ""),
        "state_id": top.get("state_id", ""),
        "win_rate": top.get("win_rate", 0),
        "vec_score": top.get("vec_score", 0),
        "sas": top.get("sas", 0),
        "bitmask_score": top.get("bitmask_score", 1.0),
        "final_score": top.get("final_score", 0),
        "confidence": top.get("confidence", 1.0),
        "extraction_method": result["extraction"].get("method", "unknown"),
        "conversation_state": result["merged"],
        "ranking_weights": get_ranking_weights(),
        "fallbacks": top.get("fallbacks", []),
        "latency_ms": result["latency_ms"],
    }

    await sio.emit("recommendation", {"session_id": session_id, **response}, room=sid)
    return response


@sio.on("collector_turn")
async def collector_turn(sid, data):
    try:
        payload = _validate_collector_turn(data or {})
    except ValueError as e:
        return {"error": "invalid payload", "detail": str(e)}
    session_id = payload.session_id
    session = sessions.get(session_id)
    if not session:
        return {"error": "session not found"}

    utterance = payload.utterance
    async with sessions.lock(session_id):
        extraction = await extract_state(utterance, app.state.taxonomy, db=app.state.db)
        new_actions = extraction.get("actions", [])
        merged = merge_state(session["conversation_state"], {"facts": [], "emotions": [], "actions": new_actions})
        session["conversation_state"] = merged

        session["transcript"].append({
            "turn": len(session["transcript"]) + 1,
            "role": "collector",
            "utterance": utterance,
            "extracted_actions": new_actions,
        })

        db = _get_db()
        if db is not None:
            try:
                turn_idx = len(session["transcript"])
                await db.append_transcript_turn(session_id, turn_idx, "collector", utterance, {"extracted_actions": new_actions})
                await db.save_session(session_id, session["cust_no"], session["context"], session["conversation_state"], call_info=session.get("call_info"), agent=session.get("agent"))
            except Exception:
                _log.warning("failed to persist turn for session %s", session_id, exc_info=True)

    return {"recorded": True, "extracted_actions": new_actions, "conversation_state": merged}


@sio.on("end_session")
async def end_session(sid, data):
    session_id = (data or {}).get("session_id", "")
    session = _end_session(session_id)
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


from f010_api_mock_ui.debug import debug_recommend


@app.post("/recommend/debug")
async def debug_endpoint(req: RecommendRequest):
    req_dict = {
        "customer_utterance": req.customer_utterance,
        "conversation_context": req.conversation_context,
        "conversation_state": {
            "branch_key": req.conversation_state.branch_key,
            "inherited_facts": req.conversation_state.inherited_facts,
            "inherited_emotions": req.conversation_state.inherited_emotions,
            "willingness": req.conversation_state.willingness,
        },
        "context": req.context,
    }
    return await debug_recommend(req_dict, app.state)


from fastapi.staticfiles import StaticFiles

_ui_dir = os.path.join(os.path.dirname(__file__), "..", "f010_api_mock_ui", "ui")
app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")

app.mount("/socket.io", socketio.ASGIApp(sio))
