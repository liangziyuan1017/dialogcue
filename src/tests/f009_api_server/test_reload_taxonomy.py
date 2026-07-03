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
        mock_db.ping = AsyncMock(return_value=True)
        mock_db.load_taxonomy_from_db = AsyncMock(return_value={"facts": [{"group_name": "new_kw"}], "emotions": [], "collector_actions": []})
        mock_db_init.return_value = mock_db
        mock_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        mock_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        from f009_api_server.server import app
        with TestClient(app) as client:
            yield client


class TestReloadTaxonomy:
    def test_reload_taxonomy_endpoint(self, client):
        resp = client.post("/admin/reload-taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reloaded"] is True

    def test_reload_taxonomy_updates_app_state(self, client):
        from f009_api_server.server import app
        client.post("/admin/reload-taxonomy")
        tax = app.state.taxonomy
        assert any(g.get("group_name") == "new_kw" for g in tax.get("facts", []))
