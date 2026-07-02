from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from f007_infrastructure.embeddings import EMBEDDING_DIM


@pytest.fixture
def client():
    with patch("f009_api_server.server._init_db") as mock_db_init, \
         patch("f009_api_server.server._init_taxonomy") as mock_tax, \
         patch("f009_api_server.server._load_scored_tree") as mock_tree:
        mock_db_init.return_value = MagicMock()
        mock_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        mock_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        from f009_api_server.server import app
        app.state.db = MagicMock()
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.label_set_index = {}
        client = TestClient(app)
        yield client


def _valid_payload():
    return {
        "customer_utterance": "我现在没钱还",
        "conversation_context": "",
        "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
        "context": {"has_auto_loan": False, "has_mortgage": True},
    }


def test_response_has_request_id_header(client):
    with patch("f009_api_server.server.extract_state", return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}), \
         patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
         patch("f009_api_server.server.recommend", return_value={
             "script_text": "s", "script_id": "s1", "state_id": "", "win_rate": 0, "vec_score": 0,
              "sas": 0, "final_score": 0, "confidence": 0.5, "ranking_weights": {}, "node_retrieved": [],
              "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
          }):
        resp = client.post("/recommend", json=_valid_payload())
    assert resp.status_code == 200
    assert "x-request-id" in {k.lower() for k in resp.headers.keys()}
    assert resp.headers["x-request-id"]


def test_inbound_request_id_is_echoed(client):
    inbound = "req-inbound-xyz"
    with patch("f009_api_server.server.extract_state", return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}), \
         patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
         patch("f009_api_server.server.recommend", return_value={
              "script_text": "s", "script_id": "s1", "state_id": "", "win_rate": 0, "vec_score": 0,
              "sas": 0, "final_score": 0, "confidence": 0.5, "ranking_weights": {}, "node_retrieved": [],
             "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
         }):
        resp = client.post("/recommend", json=_valid_payload(), headers={"X-Request-ID": inbound})
    assert resp.headers["x-request-id"] == inbound


def test_request_id_bound_in_log_context(client):
    from f007_infrastructure import logging as applog
    captured = {}
    original = applog.get_request_id

    def spy():
        captured["rid"] = applog.get_request_id()
        return original()

    with patch("f009_api_server.server.extract_state", return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}), \
         patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
         patch("f009_api_server.server.recommend", side_effect=lambda **kw: (spy(), {
             "script_text": "s", "script_id": "s1", "state_id": "", "win_rate": 0, "vec_score": 0,
              "sas": 0, "final_score": 0, "confidence": 0.5, "ranking_weights": {}, "node_retrieved": [],
             "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
         })[1]):
        resp = client.post("/recommend", json=_valid_payload(), headers={"X-Request-ID": "req-ctx-1"})
    assert resp.status_code == 200
    assert captured.get("rid") == "req-ctx-1"
