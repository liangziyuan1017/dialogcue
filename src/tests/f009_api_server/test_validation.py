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


def _valid_body(utterance="我现在没钱还", context=""):
    return {
        "customer_utterance": utterance,
        "conversation_context": context,
        "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
        "context": {"has_auto_loan": False, "has_mortgage": True},
    }


class TestInputValidation:
    def test_oversize_utterance_returns_422(self, client):
        resp = client.post("/recommend", json=_valid_body(utterance="x" * 100000))
        assert resp.status_code == 422

    def test_oversize_conversation_context_returns_422(self, client):
        resp = client.post("/recommend", json=_valid_body(context="x" * 100000))
        assert resp.status_code == 422

    def test_oversize_returns_structured_error(self, client):
        resp = client.post("/recommend", json=_valid_body(utterance="x" * 100000))
        data = resp.json()
        assert "detail" in data


class TestSocketEventValidation:
    def test_start_session_rejects_malformed_payload(self, client):
        from f009_api_server.server import _validate_start_session
        with pytest.raises(ValueError):
            _validate_start_session({"cust_no": "0100", "context": "not-a-dict"})

    def test_start_session_accepts_valid(self, client):
        from f009_api_server.server import _validate_start_session
        result = _validate_start_session({"cust_no": "0100", "context": {}})
        assert result.cust_no == "0100"

    def test_customer_turn_rejects_missing_session_id(self, client):
        from f009_api_server.server import _validate_customer_turn
        with pytest.raises(ValueError):
            _validate_customer_turn({"utterance": "hi"})

    def test_customer_turn_rejects_oversize(self, client):
        from f009_api_server.server import _validate_customer_turn
        with pytest.raises(ValueError):
            _validate_customer_turn({"session_id": "s1", "utterance": "x" * 100000})
