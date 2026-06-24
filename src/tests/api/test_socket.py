import pytest
from unittest.mock import MagicMock, patch
from api.server import sessions


class TestSocketHandlers:
    def test_start_session(self):
        sessions.clear()
        from api.server import start_session
        result = start_session("sid1", {"cust_no": "0100252354", "context": {}})
        assert "session_id" in result
        assert result["session_id"].startswith("sess_")
        assert result["conversation_state"]["facts"] == []

    def test_end_session_returns_transcript(self):
        sessions.clear()
        from api.server import start_session, end_session
        start_result = start_session("sid1", {"cust_no": "0100252354", "context": {}})
        session_id = start_result["session_id"]
        end_result = end_session("sid1", {"session_id": session_id})
        assert "duration_seconds" in end_result
        assert "turn_count" in end_result
        assert "transcript" in end_result
        assert "final_conversation_state" in end_result

    def test_session_not_found(self):
        sessions.clear()
        from api.server import end_session
        result = end_session("sid1", {"session_id": "nonexistent"})
        assert "error" in result

    def test_collector_turn_extracts_actions(self):
        sessions.clear()
        from api.server import start_session, collector_turn, app
        app.state.db = MagicMock()
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        start_result = start_session("sid1", {"cust_no": "0100252354", "context": {}})
        session_id = start_result["session_id"]
        with patch("api.server.extract_state", return_value={"facts": [], "emotions": [], "actions": ["empathy"], "confidence": 0.8, "method": "llm"}):
            result = collector_turn("sid1", {"session_id": session_id, "utterance": "我理解您的困难"})
        assert result["recorded"] is True
        assert "empathy" in result["extracted_actions"]
        assert "empathy" in result["conversation_state"]["actions"]
