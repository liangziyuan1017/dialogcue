import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from f009_api_server.server import app, sessions


def _setup_app_state():
    app.state.db = MagicMock()
    app.state.db.append_transcript_turn = AsyncMock()
    app.state.db.save_session = AsyncMock()
    app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
    app.state.tree = {}
    app.state.index = {}
    app.state.label_set_index = {}


def test_run_turn_valid_session():
    sessions.clear()
    _setup_app_state()
    sid = sessions.create(cust_no="c1", context={})
    fake_extraction = {"facts": ["f1"], "emotions": ["e1"], "actions": [], "method": "llm"}
    fake_merged = {"branch_key": {}, "inherited_facts": ["f1"], "inherited_emotions": ["e1"], "willingness": None}
    fake_rec = {"script_text": "hello", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
    with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
         patch("f009_api_server.server.merge_state", return_value=fake_merged), \
         patch("f009_api_server.server.embed_single", return_value=[0.0] * 128), \
         patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
        from f009_api_server.server import _run_turn
        result = asyncio.run(_run_turn(sid, "客户说话", "客户说话"))
    assert result is not None
    assert result["extraction"] == fake_extraction
    assert result["merged"] == fake_merged
    assert result["rec_result"] == fake_rec
    assert "latency_ms" in result
    assert result["entry"]["turn"] == 1
    assert result["entry"]["role"] == "customer"
    assert result["entry"]["utterance"] == "客户说话"


def test_run_turn_unknown_session():
    sessions.clear()
    _setup_app_state()
    from f009_api_server.server import _run_turn
    result = asyncio.run(_run_turn("nonexistent", "text", "text"))
    assert result is None


def test_run_turn_updates_conversation_state():
    sessions.clear()
    _setup_app_state()
    sid = sessions.create(cust_no="c1", context={})
    fake_extraction = {"facts": ["f1"], "emotions": [], "actions": [], "method": "llm"}
    fake_merged = {"branch_key": {}, "inherited_facts": ["f1"], "inherited_emotions": [], "willingness": None}
    with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
         patch("f009_api_server.server.merge_state", return_value=fake_merged), \
         patch("f009_api_server.server.embed_single", return_value=[0.0] * 128), \
         patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
        from f009_api_server.server import _run_turn
        asyncio.run(_run_turn(sid, "text", "text"))
    session = sessions.get(sid)
    assert session["conversation_state"] == fake_merged


def test_run_turn_appends_transcript_entry():
    sessions.clear()
    _setup_app_state()
    sid = sessions.create(cust_no="c1", context={})
    fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
    fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
    with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
         patch("f009_api_server.server.merge_state", return_value=fake_merged), \
         patch("f009_api_server.server.embed_single", return_value=[0.0] * 128), \
         patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
        from f009_api_server.server import _run_turn
        asyncio.run(_run_turn(sid, "first", "first"))
        asyncio.run(_run_turn(sid, "second", "first second"))
    session = sessions.get(sid)
    assert len(session["transcript"]) == 2
    assert session["transcript"][0]["turn"] == 1
    assert session["transcript"][1]["turn"] == 2


def test_run_turn_persists_to_db():
    sessions.clear()
    _setup_app_state()
    sid = sessions.create(cust_no="c1", context={})
    fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
    fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
    with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
         patch("f009_api_server.server.merge_state", return_value=fake_merged), \
         patch("f009_api_server.server.embed_single", return_value=[0.0] * 128), \
         patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
        from f009_api_server.server import _run_turn
        asyncio.run(_run_turn(sid, "text", "text"))
    app.state.db.append_transcript_turn.assert_awaited_once()
    app.state.db.save_session.assert_awaited_once()
