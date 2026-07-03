from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _boot(ready=True, tree_ok=True, taxonomy_ok=True):
    with patch("f009_api_server.server._init_db") as m_db, \
         patch("f009_api_server.server._init_taxonomy") as m_tax, \
         patch("f009_api_server.server._load_scored_tree") as m_tree:
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.create_tables = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.ping = AsyncMock(return_value=True)
        m_db.return_value = mock_db
        if taxonomy_ok:
            m_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
        else:
            m_tax.side_effect = RuntimeError("taxonomy missing")
        if tree_ok:
            m_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        else:
            m_tree.side_effect = RuntimeError("tree missing")
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-real" if ready else "sk-placeholder"}):
            from f009_api_server.server import app
            with TestClient(app) as c:
                yield c


class TestHealthEndpoints:
    def test_health_returns_200(self):
        for c in _boot():
            resp = c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "up"
            break

    def test_readyz_200_when_ready(self):
        for c in _boot(ready=True):
            resp = c.get("/readyz")
            assert resp.status_code == 200
            assert resp.json()["ready"] is True
            break

    def test_readyz_503_when_not_ready(self):
        for c in _boot(ready=False):
            resp = c.get("/readyz")
            assert resp.status_code == 503
            assert resp.json()["ready"] is False
            break

    def test_readyz_503_when_tree_missing(self):
        for c in _boot(tree_ok=False):
            resp = c.get("/readyz")
            assert resp.status_code == 503
            break

    def test_recommend_503_when_not_ready(self):
        for c in _boot(ready=False):
            resp = c.post("/recommend", json={
                "customer_utterance": "hi",
                "conversation_context": "",
                "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
                "context": {},
            })
            assert resp.status_code == 503
            break


class TestCors:
    def test_cors_header_present(self):
        for c in _boot():
            resp = c.options("/recommend", headers={"Origin": "http://example.com", "Access-Control-Request-Method": "POST"})
            assert "access-control-allow-origin" in {k.lower() for k in resp.headers}
            break
