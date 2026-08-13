from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _boot_with(env_key):
    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": env_key}, clear=False):
        with patch("f009_api_server.server._init_db") as m_db, \
             patch("f009_api_server.server._init_taxonomy") as m_tax, \
             patch("f009_api_server.server._load_scored_tree") as m_tree:
            mock_db = MagicMock()
            mock_db.connect = AsyncMock()
            mock_db.create_tables = AsyncMock()
            mock_db.close = AsyncMock()
            m_db.return_value = mock_db
            m_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
            m_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
            from f009_api_server.server import app
            with TestClient(app):
                return getattr(app.state, "ready", None), getattr(app.state, "ready_reason", None)


def test_placeholder_key_marks_not_ready():
    ready, reason = _boot_with("sk-placeholder")
    assert ready is False
    assert reason and "placeholder" in reason.lower()


def test_real_key_boots_ready():
    ready, _ = _boot_with("sk-real-abc123notplaceholder")
    assert ready is True


def test_real_key_boot_does_not_materialize_scored_tree():
    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-real-abc123notplaceholder"}, clear=False), \
         patch("f009_api_server.server._init_db") as m_db, \
         patch("f009_api_server.server._init_taxonomy") as m_tax, \
         patch("f009_api_server.server._load_scored_tree") as m_tree:
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.create_tables = AsyncMock()
        mock_db.close = AsyncMock()
        m_db.return_value = mock_db
        m_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}

        from f009_api_server.server import app
        with TestClient(app):
            assert not hasattr(app.state, "tree")
            assert not hasattr(app.state, "index")
            assert not hasattr(app.state, "label_set_index")
        m_tree.assert_not_called()
