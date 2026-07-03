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


class TestExternalSessionStart:
    def test_valid_payload_returns_200(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        resp = client.post("/api/v1/session/start", json={
            "call_id": "call_001",
            "call_info": {},
            "agent": {},
            "customer": {"cust_no": "0100252354"},
            "cust_tags": [],
        })
        assert resp.status_code == 200
        assert resp.json()["call_id"] == "call_001"

    def test_call_id_used_as_session_id(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        client.post("/api/v1/session/start", json={
            "call_id": "call_002",
            "customer": {"cust_no": "c1"},
            "cust_tags": [],
        })
        assert sessions.get("call_002") is not None

    def test_cust_tags_mapped_to_context(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        client.post("/api/v1/session/start", json={
            "call_id": "call_003",
            "customer": {"cust_no": "c1"},
            "cust_tags": [{"tag": "经营贷款余额", "value": "5000"}],
        })
        session = sessions.get("call_003")
        assert session["context"]["has_auto_loan"] is True

    def test_call_info_and_agent_stored_in_session(self, client):
        from f009_api_server.server import sessions
        sessions.clear()
        client.post("/api/v1/session/start", json={
            "call_id": "call_006",
            "call_info": {"dial_type": "1", "channel": "X"},
            "agent": {"coll_user_id": "AA11100", "coll_area": "2"},
            "customer": {"cust_no": "c1"},
            "cust_tags": [],
        })
        session = sessions.get("call_006")
        assert session["call_info"] == {"dial_type": "1", "channel": "X"}
        assert session["agent"] == {"coll_user_id": "AA11100", "coll_area": "2"}

    def test_missing_call_id_returns_422(self, client):
        resp = client.post("/api/v1/session/start", json={
            "customer": {"cust_no": "c1"},
            "cust_tags": [],
        })
        assert resp.status_code == 422

    def test_oversize_call_id_returns_422(self, client):
        resp = client.post("/api/v1/session/start", json={
            "call_id": "x" * 10000,
            "customer": {"cust_no": "c1"},
            "cust_tags": [],
        })
        assert resp.status_code == 422

    def test_oversize_cust_tags_returns_422(self, client):
        resp = client.post("/api/v1/session/start", json={
            "call_id": "call_005",
            "customer": {"cust_no": "c1"},
            "cust_tags": [{"tag": "x", "value": "y"}] * 600,
        })
        assert resp.status_code == 422

    def test_not_ready_returns_503(self, client):
        from f009_api_server.server import app
        app.state.ready = False
        app.state.ready_reason = "boot error"
        app.state.boot_errors = ["boot error"]
        resp = client.post("/api/v1/session/start", json={
            "call_id": "call_004",
            "customer": {"cust_no": "c1"},
            "cust_tags": [],
        })
        assert resp.status_code == 503
