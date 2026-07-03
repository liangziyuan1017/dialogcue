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


def _start_session(client, call_id="call_001"):
    client.post("/api/v1/session/start", json={
        "call_id": call_id,
        "customer": {"cust_no": "c1"},
        "cust_tags": [],
    })


class TestExternalRecommend:
    def test_valid_request_returns_200(self, client):
        _start_session(client)
        fake_extraction = {"facts": ["f1"], "emotions": ["e1"], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": ["f1"], "inherited_emotions": ["e1"], "willingness": None}
        fake_rec = {"script_text": "建议", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "客户说话",
                "history_context": [],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendation" in data
        assert "state_tags" in data
        assert "confidence" in data
        assert "rec_id" in data
        assert "info" in data

    def test_recommendation_is_script_text(self, client):
        _start_session(client)
        fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        fake_rec = {"script_text": "你好", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "text",
                "history_context": [],
            })
        assert resp.json()["recommendation"] == "你好"

    def test_recommendation_null_when_no_match(self, client):
        _start_session(client)
        fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "text",
                "history_context": [],
            })
        assert resp.status_code == 200
        assert resp.json()["recommendation"] is None

    def test_state_tags_contains_facts_and_emotions(self, client):
        _start_session(client)
        fake_extraction = {"facts": ["f1", "f2"], "emotions": ["e1"], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        fake_rec = {"script_text": "x", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "text",
                "history_context": [],
            })
        assert resp.json()["state_tags"] == ["f1", "f2", "e1"]

    def test_rec_id_format(self, client):
        _start_session(client)
        fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        fake_rec = {"script_text": "x", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=fake_rec):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "text",
                "history_context": [],
            })
        assert resp.json()["rec_id"] == "rec_call_001_001"

    def test_unknown_call_id_returns_404(self, client):
        resp = client.post("/api/v1/recommend", json={
            "call_id": "nonexistent",
            "current_text": "text",
            "history_context": [],
        })
        assert resp.status_code == 404

    def test_history_context_included_in_conv_ctx(self, client):
        _start_session(client)
        fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        fake_rec = {"script_text": "x", "script_id": "s1", "final_score": 0.9, "confidence": 0.8}
        captured = {}
        async def fake_run_turn(session_id, utterance, conv_ctx):
            captured["conv_ctx"] = conv_ctx
            return {"extraction": fake_extraction, "merged": fake_merged, "rec_result": fake_rec, "latency_ms": 1, "entry": {"turn": 1, "role": "customer", "utterance": utterance}}
        with patch("f009_api_server.server._run_turn", side_effect=fake_run_turn):
            resp = client.post("/api/v1/recommend", json={
                "call_id": "call_001",
                "current_text": "现在",
                "history_context": ["之前", "的话"],
            })
        assert resp.status_code == 200
        assert "之前" in captured["conv_ctx"]
        assert "的话" in captured["conv_ctx"]
        assert "现在" in captured["conv_ctx"]

    def test_oversize_current_text_returns_422(self, client):
        _start_session(client)
        resp = client.post("/api/v1/recommend", json={
            "call_id": "call_001",
            "current_text": "x" * 10000,
            "history_context": [],
        })
        assert resp.status_code == 422

    def test_oversize_call_id_returns_422(self, client):
        resp = client.post("/api/v1/recommend", json={
            "call_id": "x" * 10000,
            "current_text": "text",
            "history_context": [],
        })
        assert resp.status_code == 422

    def test_oversize_history_context_returns_422(self, client):
        _start_session(client)
        resp = client.post("/api/v1/recommend", json={
            "call_id": "call_001",
            "current_text": "text",
            "history_context": ["x"] * 200,
        })
        assert resp.status_code == 422

    def test_not_ready_returns_503(self, client):
        from f009_api_server.server import app
        app.state.ready = False
        app.state.ready_reason = "boot error"
        app.state.boot_errors = ["boot error"]
        resp = client.post("/api/v1/recommend", json={
            "call_id": "call_001",
            "current_text": "text",
            "history_context": [],
        })
        assert resp.status_code == 503

    def test_rate_limit_returns_429(self, client):
        from f009_api_server.server import _rate_limiter, sessions
        from f009_api_server.rate_limit import RateLimiter
        sessions.clear()
        sessions.create_with_id("call_rl", cust_no="c1", context={})
        tiny = RateLimiter(rate_rps=0, burst=2, clock=MagicMock(side_effect=[0.0] * 100))
        fake_extraction = {"facts": [], "emotions": [], "actions": [], "method": "llm"}
        fake_merged = {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}
        client.__enter__()
        with patch.object(_rate_limiter, "allow", side_effect=tiny.allow), \
             patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value=fake_extraction), \
             patch("f009_api_server.server.merge_state", return_value=fake_merged), \
             patch("f009_api_server.server.embed_single", return_value=[0.0] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
            r1 = client.post("/api/v1/recommend", json={"call_id": "call_rl", "current_text": "a"})
            r2 = client.post("/api/v1/recommend", json={"call_id": "call_rl", "current_text": "b"})
            r3 = client.post("/api/v1/recommend", json={"call_id": "call_rl", "current_text": "c"})
        client.__exit__(None, None, None)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
