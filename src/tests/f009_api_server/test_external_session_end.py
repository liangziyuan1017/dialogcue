from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


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


class TestExternalSessionEnd:
    def test_valid_call_id_returns_200(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        sessions.create_with_id("call_001", cust_no="c1", context={})
        resp = client.delete("/api/v1/session/end?call_id=call_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["message"] == "session closed"
        assert data["call_id"] == "call_001"

    def test_unknown_call_id_returns_404(self, client):
        resp = client.delete("/api/v1/session/end?call_id=nonexistent")
        assert resp.status_code == 404

    def test_missing_call_id_returns_422(self, client):
        resp = client.delete("/api/v1/session/end")
        assert resp.status_code == 422

    def test_session_removed_from_store(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        sessions.create_with_id("call_002", cust_no="c1", context={})
        client.delete("/api/v1/session/end?call_id=call_002")
        assert sessions.get("call_002") is None
