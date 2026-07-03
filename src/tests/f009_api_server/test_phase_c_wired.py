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
        from f009_api_server.server import app, _rate_limiter
        app.state.db = mock_db
        app.state.taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
        app.state.tree = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
        app.state.index = {}
        app.state.label_set_index = {}
        client = TestClient(app)
        yield client


def _valid_body():
    return {
        "customer_utterance": "我现在没钱还",
        "conversation_context": "",
        "conversation_state": {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
        "context": {"has_auto_loan": False, "has_mortgage": True},
    }


class TestRateLimitWired:
    def test_429_when_rate_limit_exceeded(self, client):
        from f009_api_server.server import _rate_limiter
        from f009_api_server.rate_limit import RateLimiter
        client.__enter__()
        tiny = RateLimiter(rate_rps=0, burst=2, clock=MagicMock(side_effect=[0.0] * 100))
        orig = _rate_limiter._buckets
        with patch.object(_rate_limiter, "allow", side_effect=tiny.allow):
            with patch("f009_api_server.server.extract_state", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}), \
                 patch("f009_api_server.server.embed_single", return_value=[0.1] * EMBEDDING_DIM), \
                 patch("f009_api_server.server.recommend", new_callable=AsyncMock, return_value=None):
                r1 = client.post("/recommend", json=_valid_body())
                r2 = client.post("/recommend", json=_valid_body())
                r3 = client.post("/recommend", json=_valid_body())
        client.__exit__(None, None, None)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429


class TestSocketValidationWired:
    def test_customer_turn_oversize_returns_structured_error(self, client):
        from f009_api_server.server import start_session, customer_turn, sessions
        sessions.clear()
        client.__enter__()
        start = start_session.__wrapped__ if hasattr(start_session, "__wrapped__") else start_session
        import asyncio
        sr = asyncio.run(start_session("sid", {"cust_no": "c", "context": {}}))
        sid = sr["session_id"]
        result = asyncio.run(customer_turn("sid", {"session_id": sid, "utterance": "x" * 100000}))
        client.__exit__(None, None, None)
        assert "error" in result
