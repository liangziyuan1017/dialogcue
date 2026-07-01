import os
import tempfile

import pytest

from f007_infrastructure import config as cfgmod
from f007_infrastructure.config import ConfigError, _parse_frontmatter


def test_missing_closing_fence_raises_config_error_with_path():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("---\nranking_weights:\n  win_rate: 0.5\n")
        path = f.name
    try:
        with pytest.raises(ConfigError) as exc:
            _parse_frontmatter(path)
        assert path in str(exc.value) or "fence" in str(exc.value).lower()
    finally:
        os.unlink(path)


def test_config_error_is_value_error_subclass():
    assert issubclass(ConfigError, ValueError)


def test_load_config_propagates_config_error(monkeypatch):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("---\nkey: val\n")
        path = f.name
    monkeypatch.setenv("CONFIG_PATH", path)
    cfgmod._cache = None
    cfgmod._validated = False
    try:
        with pytest.raises(ConfigError):
            cfgmod.load_config()
    finally:
        os.unlink(path)
        cfgmod._cache = None
        cfgmod._validated = False
