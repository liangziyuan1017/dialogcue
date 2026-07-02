from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from f007_infrastructure.embeddings import EMBEDDING_DIM


def _mock_app():
    from f009_api_server.server import app
    return TestClient(app)


@pytest.fixture
def client():
    with patch("f009_api_server.server._init_db") as mock_db_init, \
         patch("f009_api_server.server._init_taxonomy") as mock_tax, \
         patch("f009_api_server.server._load_scored_tree") as mock_tree:
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.create_tables = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db_init.return_value = mock_db
        mock_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        mock_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        from f009_api_server.server import app
        app.state.db = mock_db
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.label_set_index = {}
        client = TestClient(app)
        yield client


class TestRecommendEndpoint:
    def test_returns_200_with_valid_input(self, client):
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": ["financial_hardship"], "emotions": [], "actions": [], "confidence": 0.9, "method": "llm"}), \
             patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value={
                 "script_text": "建议还款", "script_id": "s1", "state_id": "financial_hardship",
                 "win_rate": 0.8, "vec_score": 0.9, "sas": 0.7, "final_score": 0.82,
                 "confidence": 0.9, "ranking_weights": {}, "node_retrieved": [],
                 "conversation_state": {"branch_key": {"facts": ["financial_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
             }):
            resp = client.post("/recommend", json={
                "customer_utterance": "我现在没钱还",
                "conversation_context": "",
                "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
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
        with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": ["financial_hardship"], "emotions": ["pleading"], "actions": [], "confidence": 0.9, "method": "llm"}), \
             patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
             patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value={
                 "script_text": "建议还款", "script_id": "s1", "state_id": "financial_hardship",
                 "win_rate": 0.8, "vec_score": 0.9, "sas": 0.7, "final_score": 0.82,
                 "confidence": 0.9, "ranking_weights": {}, "node_retrieved": [],
                 "conversation_state": {"branch_key": {"emotions": ["pleading"]}, "inherited_facts": ["request_installment", "financial_hardship"], "inherited_emotions": [], "willingness": "conditional"},
             }):
            resp = client.post("/recommend", json={
                "customer_utterance": "我现在没钱还",
                "conversation_context": "",
                "conversation_state": {"branch_key": {"facts": ["request_installment"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
                "context": {"has_auto_loan": False, "has_mortgage": True},
            })
        data = resp.json()
        cs = data["conversation_state"]
        assert "branch_key" in cs
        assert "inherited_facts" in cs
        assert "inherited_emotions" in cs
