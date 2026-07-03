import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from f007_infrastructure.embeddings import EMBEDDING_DIM
from f009_api_server.server import sessions


def _setup_db_mock():
    db = MagicMock()
    db.save_session = AsyncMock()
    db.append_transcript_turn = AsyncMock()
    db.load_session = AsyncMock()
    db.load_transcript_turns = AsyncMock()
    return db


class TestCreateSession:
    def test_create_session_with_explicit_id(self):
        sessions.clear()
        from f009_api_server.server import _create_session, app
        app.state.db = _setup_db_mock()
        sid = asyncio.run(_create_session("c1", {"k": "v"}, session_id="call_123"))
        assert sid == "call_123"
        assert sessions.get("call_123") is not None

    def test_create_session_auto_generates_id(self):
        sessions.clear()
        from f009_api_server.server import _create_session, app
        app.state.db = _setup_db_mock()
        sid = asyncio.run(_create_session("c1", {}))
        assert sid.startswith("sess_")

    def test_create_session_persists_to_db(self):
        sessions.clear()
        from f009_api_server.server import _create_session, app
        db = _setup_db_mock()
        app.state.db = db
        asyncio.run(_create_session("c1", {"k": "v"}, session_id="call_456"))
        db.save_session.assert_awaited_once()


class TestEndSession:
    def test_end_session_returns_session_dict(self):
        sessions.clear()
        from f009_api_server.server import _create_session, _end_session, app
        app.state.db = _setup_db_mock()
        asyncio.run(_create_session("c1", {}, session_id="call_789"))
        result = _end_session("call_789")
        assert result is not None
        assert result["cust_no"] == "c1"
        assert sessions.get("call_789") is None

    def test_end_session_unknown_returns_none(self):
        sessions.clear()
        from f009_api_server.server import _end_session
        result = _end_session("nonexistent")
        assert result is None


class TestStartSessionPersistsToDB:
    def test_start_session_calls_save_session(self):
        sessions.clear()
        from f009_api_server.server import app, start_session
        db = _setup_db_mock()
        app.state.db = db
        result = asyncio.run(start_session("sid1", {"cust_no": "c1", "context": {"k": "v"}}))
        db.save_session.assert_awaited_once()
        sid = result["session_id"]
        call_args = db.save_session.call_args.args
        assert call_args[0] == sid
        assert call_args[1] == "c1"
        assert call_args[2] == {"k": "v"}

    def test_start_session_without_db_does_not_crash(self):
        sessions.clear()
        from f009_api_server.server import app, start_session
        if hasattr(app.state, "_db"):
            del app.state._db
        result = asyncio.run(start_session("sid1", {"cust_no": "c1", "context": {}}))
        assert "session_id" in result


class TestCustomerTurnPersistsToDB:
    def test_customer_turn_calls_append_transcript_and_save(self):
        sessions.clear()
        from f009_api_server.server import app, customer_turn, start_session
        db = _setup_db_mock()
        app.state.db = db
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.label_set_index = {}
        sr = asyncio.run(start_session("sid", {"cust_no": "c", "context": {}}))
        session_id = sr["session_id"]
        db.save_session.reset_mock()
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}), \
             patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value={"script_text": "s", "script_id": "s1", "final_score": 0.5}):
            asyncio.run(customer_turn("sid", {"session_id": session_id, "utterance": "test"}))
        db.append_transcript_turn.assert_awaited_once()
        turn_args = db.append_transcript_turn.call_args.args
        assert turn_args[0] == session_id
        assert turn_args[2] == "customer"
        assert turn_args[3] == "test"
        db.save_session.assert_awaited_once()


class TestCollectorTurnPersistsToDB:
    def test_collector_turn_calls_append_transcript_and_save(self):
        sessions.clear()
        from f009_api_server.server import app, collector_turn, start_session
        db = _setup_db_mock()
        app.state.db = db
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        sr = asyncio.run(start_session("sid", {"cust_no": "c", "context": {}}))
        session_id = sr["session_id"]
        db.save_session.reset_mock()
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": ["empathy"], "confidence": 0.8, "method": "llm"}):
            asyncio.run(collector_turn("sid", {"session_id": session_id, "utterance": "我理解"}))
        db.append_transcript_turn.assert_awaited_once()
        db.save_session.assert_awaited_once()


class TestResumeSession:
    def test_resume_recovers_from_db(self):
        sessions.clear()
        from f009_api_server.server import app, resume_session
        db = _setup_db_mock()
        db.load_session.return_value = {
            "session_id": "sess_recover",
            "cust_no": "c1",
            "context": {"k": "v"},
            "conversation_state": {"branch_key": {"action": "empathy"}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
            "start_time": datetime(2026, 7, 3, 10, 0, 0),
            "last_active": datetime(2026, 7, 3, 10, 0, 0),
        }
        db.load_transcript_turns.return_value = [
            {"turn": 1, "role": "customer", "utterance": "hello"},
            {"turn": 2, "role": "collector", "utterance": "ok"},
        ]
        app.state.db = db
        result = asyncio.run(resume_session("sid", {"session_id": "sess_recover"}))
        assert result["session_id"] == "sess_recover"
        assert result["recovered"] is True
        assert len(result["transcript"]) == 2
        assert result["transcript"][0]["utterance"] == "hello"
        assert result["conversation_state"]["branch_key"] == {"action": "empathy"}
        assert sessions.get("sess_recover") is not None

    def test_resume_already_in_memory(self):
        sessions.clear()
        from f009_api_server.server import resume_session, start_session
        sr = asyncio.run(start_session("sid", {"cust_no": "c", "context": {}}))
        session_id = sr["session_id"]
        result = asyncio.run(resume_session("sid", {"session_id": session_id}))
        assert result["recovered"] is False
        assert "transcript" in result

    def test_resume_not_found_in_db(self):
        sessions.clear()
        from f009_api_server.server import app, resume_session
        db = _setup_db_mock()
        db.load_session.return_value = None
        app.state.db = db
        result = asyncio.run(resume_session("sid", {"session_id": "nonexistent"}))
        assert "error" in result

    def test_resume_without_db_returns_error(self):
        sessions.clear()
        from f009_api_server.server import app, resume_session
        if hasattr(app.state, "_db"):
            del app.state._db
        result = asyncio.run(resume_session("sid", {"session_id": "sess_x"}))
        assert "error" in result

    def test_resume_missing_session_id(self):
        sessions.clear()
        from f009_api_server.server import resume_session
        result = asyncio.run(resume_session("sid", {}))
        assert "error" in result

    def test_resume_with_timezone_aware_start_time_survives_eviction(self):
        sessions.clear()
        from datetime import UTC

        from f009_api_server.server import app, resume_session
        db = _setup_db_mock()
        db.load_session.return_value = {
            "session_id": "sess_tz",
            "cust_no": "c1",
            "context": {},
            "conversation_state": {},
            "start_time": datetime(2026, 7, 3, 10, 0, 0, tzinfo=UTC),
            "last_active": datetime(2026, 7, 3, 10, 0, 0, tzinfo=UTC),
        }
        db.load_transcript_turns.return_value = []
        app.state.db = db
        asyncio.run(resume_session("sid", {"session_id": "sess_tz"}))
        sessions.evict_expired()

    def test_resume_converts_tz_aware_start_time_to_local(self):
        sessions.clear()
        from datetime import UTC

        from f009_api_server.server import app, resume_session
        db = _setup_db_mock()
        utc_time = datetime(2026, 7, 3, 10, 0, 0, tzinfo=UTC)
        db.load_session.return_value = {
            "session_id": "sess_tz2",
            "cust_no": "c1",
            "context": {},
            "conversation_state": {},
            "start_time": utc_time,
            "last_active": utc_time,
        }
        db.load_transcript_turns.return_value = []
        app.state.db = db
        asyncio.run(resume_session("sid", {"session_id": "sess_tz2"}))
        session = sessions.get("sess_tz2")
        expected_local = utc_time.astimezone().replace(tzinfo=None)
        assert session["start_time"] == expected_local

    def test_resume_reconstructs_buffer_with_leading_space(self):
        sessions.clear()
        from f009_api_server.server import app, resume_session
        db = _setup_db_mock()
        db.load_session.return_value = {
            "session_id": "sess_buf",
            "cust_no": "c1",
            "context": {},
            "conversation_state": {},
            "start_time": datetime(2026, 7, 3, 10, 0, 0),
            "last_active": datetime(2026, 7, 3, 10, 0, 0),
        }
        db.load_transcript_turns.return_value = [
            {"turn": 1, "role": "customer", "utterance": "hello"},
            {"turn": 2, "role": "collector", "utterance": "ok"},
        ]
        app.state.db = db
        asyncio.run(resume_session("sid", {"session_id": "sess_buf"}))
        session = sessions.get("sess_buf")
        assert session["conversation_context_buffer"] == " hello ok"
