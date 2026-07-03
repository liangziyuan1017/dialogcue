from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from f007_infrastructure.embeddings import EMBEDDING_DIM


@pytest.fixture
def client():
    with patch("f009_api_server.server._init_db") as mock_db_init, \
         patch("f009_api_server.server._init_taxonomy") as mock_tax, \
         patch("f009_api_server.server._load_scored_tree") as mock_tree:
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.create_tables = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.save_session = AsyncMock()
        mock_db.append_transcript_turn = AsyncMock()
        mock_db_init.return_value = mock_db
        mock_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        mock_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        from f009_api_server.server import app, sessions
        sessions.clear()
        app.state.db = mock_db
        app.state.ready = True
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.label_set_index = {}
        client = TestClient(app)
        yield client


class TestExternalApiIntegration:
    def test_full_flow_start_recommend_recommend_end(self, client):
        fake_extraction = {"facts": ["f1"], "emotions": ["e1"], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        fake_rec = {"script_text": "建议", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}

        resp = client.post("/api/v1/session/start", json={
            "call_id": "call_int_001",
            "customer": {"cust_no": "c1"},
            "cust_tags": [{"tag": "经营贷款余额", "value": "5000"}],
        })
        assert resp.status_code == 200

        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
            resp1 = client.post("/api/v1/recommend", json={
                "call_id": "call_int_001",
                "current_text": "没钱还",
                "history_context": [],
            })
            assert resp1.status_code == 200
            assert resp1.json()["rec_id"] == "rec_call_int_001_001"

            resp2 = client.post("/api/v1/recommend", json={
                "call_id": "call_int_001",
                "current_text": "真的没钱",
                "history_context": ["没钱还"],
            })
            assert resp2.status_code == 200
            assert resp2.json()["rec_id"] == "rec_call_int_001_002"

        resp_end = client.delete("/api/v1/session/end?call_id=call_int_001")
        assert resp_end.status_code == 200
        assert resp_end.json()["code"] == 0

    def test_external_endpoints_dont_break_socketio(self, client):
        from f009_api_server.server import end_session, sessions, start_session
        sessions.clear()
        result = asyncio_run(start_session("sid1", {"cust_no": "c1", "context": {}}))
        assert result["session_id"].startswith("sess_")
        end_result = asyncio_run(end_session("sid1", {"session_id": result["session_id"]}))
        assert "duration_seconds" in end_result

    def test_external_endpoints_dont_break_recommend(self, client):
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "method": "llm"}), \
             patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value={
                 "script_text": "x", "script_id": "s1", "final_score": 0.9, "confidence": 0.8,
             }):
            resp = client.post("/recommend", json={
                "customer_utterance": "hello",
                "conversation_context": "",
                "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
                "context": {"has_auto_loan": False},
            })
        assert resp.status_code == 200


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
