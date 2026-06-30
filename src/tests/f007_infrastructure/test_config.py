import os
import tempfile

import pytest

from f007_infrastructure.config import get, load_config, reload_config


def test_get_returns_config_value():
    assert get("ranking_weights.win_rate") == 0.35
    assert get("ranking_weights.vec_score") == 0.25
    assert get("ranking_weights.bitmask_score") == 0.20
    assert get("pool_cap") == 50


def test_get_returns_default_for_missing_key():
    assert get("nonexistent.key", 99) == 99
    assert get("nonexistent.key") is None


def test_get_nested_dot_notation():
    assert get("confidence.subset_drop_penalty") == 0.1
    assert get("llm.model") == "deepseek-chat"
    assert get("retry.max_retries") == 3


def test_load_config_returns_dict():
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "ranking_weights" in cfg


def test_reload_config():
    cfg1 = load_config()
    cfg2 = reload_config()
    assert isinstance(cfg2, dict)
    assert cfg2["pool_cap"] == cfg1["pool_cap"]


def test_custom_config_path(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\npool_cap: 99\nranking_weights:\n  win_rate: 0.5\n  vec_score: 0.3\n  sas: 0.1\n  bg_boost: 0.1\n---\n")
        tmp = f.name
    try:
        monkeypatch.setenv("CONFIG_PATH", tmp)
        reload_config()
        assert get("pool_cap") == 99
    finally:
        os.unlink(tmp)
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        reload_config()


def test_frontmatter_without_delimiters(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("no frontmatter here\n")
        tmp = f.name
    try:
        monkeypatch.setenv("CONFIG_PATH", tmp)
        reload_config()
        assert get("pool_cap", 50) == 50
    finally:
        os.unlink(tmp)
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        reload_config()


def test_validation_rejects_weights_not_summing_to_one(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\nranking_weights:\n  win_rate: 0.5\n  vec_score: 0.5\n  sas: 0.5\n  bg_boost: 0.5\n  bitmask_score: 0.5\n---\n")
        tmp = f.name
    try:
        monkeypatch.setenv("CONFIG_PATH", tmp)
        with pytest.raises(ValueError, match="ranking_weights sum"):
            reload_config()
    finally:
        os.unlink(tmp)
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        reload_config()


def test_validation_rejects_out_of_range(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\npool_cap: -1\n---\n")
        tmp = f.name
    try:
        monkeypatch.setenv("CONFIG_PATH", tmp)
        with pytest.raises(ValueError, match="outside range"):
            reload_config()
    finally:
        os.unlink(tmp)
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        reload_config()


def test_validation_rejects_non_numeric(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\npool_cap: abc\n---\n")
        tmp = f.name
    try:
        monkeypatch.setenv("CONFIG_PATH", tmp)
        with pytest.raises(ValueError, match="not a number"):
            reload_config()
    finally:
        os.unlink(tmp)
        monkeypatch.delenv("CONFIG_PATH", raising=False)
        reload_config()


def test_validation_passes_for_valid_config():
    reload_config()
    assert get("pool_cap") == 50
