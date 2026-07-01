from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _boot_with(env_key, app_env):
    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": env_key, "APP_ENV": app_env}, clear=False):
        with patch("f009_api_server.server._init_db") as m_db, \
             patch("f009_api_server.server._init_taxonomy") as m_tax, \
             patch("f009_api_server.server._load_scored_tree") as m_tree:
            m_db.return_value = MagicMock()
            m_tax.return_value = {"facts": [], "emotions": [], "collector_actions": []}
            m_tree.return_value = {"state_id": "root", "branch_key": {}, "inherited_facts": [], "sentence_pool": [], "children": []}
            from f009_api_server.server import app
            with TestClient(app):
                return getattr(app.state, "ready", None), getattr(app.state, "ready_reason", None)


def test_placeholder_key_in_prod_marks_not_ready():
    ready, reason = _boot_with("sk-placeholder", "prod")
    assert ready is False
    assert reason and "placeholder" in reason.lower()


def test_placeholder_key_in_dev_boots_ready():
    ready, _ = _boot_with("sk-placeholder", "dev")
    assert ready is True


def test_real_key_in_prod_boots_ready():
    ready, _ = _boot_with("sk-real-abc123notplaceholder", "prod")
    assert ready is True
