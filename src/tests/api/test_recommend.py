import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def _mock_app():
    from api.server import app
    return TestClient(app)


@pytest.fixture
def client():
    with patch("api.server._init_db") as mock_db_init, \
         patch("api.server._init_taxonomy") as mock_tax, \
         patch("api.server._init_hash_index") as mock_idx:
        mock_db_init.return_value = MagicMock()
        mock_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        mock_idx.return_value = {}
        from api.server import app
        app.state.db = MagicMock()
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.hash_index = {}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.keyword_freq = {}
        client = TestClient(app)
        yield client


class TestRecommendEndpoint:
    def test_returns_200_with_valid_input(self, client):
        app = client.app
        app.state.db.search_similar.return_value = [
            {"script_id": "s1", "script_text": "建议还款", "vec_score": 0.9, "win_rate": 0.8, "sas": 0.7, "bg_bitmask_int": 0, "bg_background": {}},
        ]
        app.state.db.get_vectors.return_value = {"s1": [0.1] * 768}
        with patch("api.server.extract_state", return_value={"facts": ["financial_hardship"], "emotions": [], "actions": [], "confidence": 0.9, "method": "llm"}), \
             patch("api.server.embed_single", return_value=[0.1] * 768):
            resp = client.post("/recommend", json={
                "customer_utterance": "我现在没钱还",
                "conversation_context": "",
                "conversation_state": {"facts": [], "emotions": [], "actions": []},
                "context": {"has_auto_loan": False, "has_mortgage": True},
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "script_text" in data
        assert "final_score" in data
        assert "vec_score" in data
        assert "conversation_state" in data
        assert "extraction_method" in data
        assert "latency_ms" in data

    def test_missing_fields_returns_422(self, client):
        resp = client.post("/recommend", json={"customer_utterance": "hello"})
        assert resp.status_code == 422

    def test_conversation_state_accumulated(self, client):
        app = client.app
        app.state.db.search_similar.return_value = [
            {"script_id": "s1", "script_text": "建议还款", "vec_score": 0.9, "win_rate": 0.8, "sas": 0.7, "bg_bitmask_int": 0, "bg_background": {}},
        ]
        app.state.db.get_vectors.return_value = {"s1": [0.1] * 768}
        with patch("api.server.extract_state", return_value={"facts": ["financial_hardship"], "emotions": ["pleading"], "actions": [], "confidence": 0.9, "method": "llm"}), \
             patch("api.server.embed_single", return_value=[0.1] * 768):
            resp = client.post("/recommend", json={
                "customer_utterance": "我现在没钱还",
                "conversation_context": "",
                "conversation_state": {"facts": ["request_installment"], "emotions": [], "actions": []},
                "context": {"has_auto_loan": False, "has_mortgage": True},
            })
        data = resp.json()
        cs = data["conversation_state"]
        assert "financial_hardship" in cs["facts"]
        assert "request_installment" in cs["facts"]
        assert "pleading" in cs["emotions"]
