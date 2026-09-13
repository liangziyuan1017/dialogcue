import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from f016_sentence_augmentation.augment_sentences import (
    load_scored_tree,
    find_node_by_id,
    find_node_by_path_signature,
    write_overlay,
    load_overlay,
    collect_existing_sentence_texts,
)


SCORED_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "../..",
    "f005_context_scoring", "data", "decision_tree_scored.json",
)


@pytest.fixture(scope="module")
def scored_tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestLoadScoredTree:
    def test_returns_dict(self):
        tree = load_scored_tree(SCORED_TREE_PATH)
        assert isinstance(tree, dict)
        assert "state_id" in tree

    def test_has_sentence_pool(self):
        tree = load_scored_tree(SCORED_TREE_PATH)
        assert "sentence_pool" in tree
        assert len(tree["sentence_pool"]) > 0


class TestFindNodeById:
    def test_finds_root_node(self, scored_tree):
        node = find_node_by_id(scored_tree, scored_tree["node_id"])
        assert node is not None
        assert node["node_id"] == scored_tree["node_id"]

    def test_finds_child_node(self, scored_tree):
        child = (scored_tree.get("children") or [None])[0]
        assert child is not None, "scored tree has no children"
        node = find_node_by_id(scored_tree, child["node_id"])
        assert node is not None
        assert node["node_id"] == child["node_id"]

    def test_returns_none_for_missing(self, scored_tree):
        node = find_node_by_id(scored_tree, "n_nonexistent")
        assert node is None


class TestFindNodeByPathSignature:
    def test_finds_root(self, scored_tree):
        node = find_node_by_path_signature(scored_tree, scored_tree["path_signature"])
        assert node is not None
        assert node["path_signature"] == scored_tree["path_signature"]

    def test_finds_child(self, scored_tree):
        child = (scored_tree.get("children") or [None])[0]
        assert child is not None, "scored tree has no children"
        node = find_node_by_path_signature(scored_tree, child["path_signature"])
        assert node is not None
        assert node["path_signature"] == child["path_signature"]

    def test_returns_none_for_missing(self, scored_tree):
        node = find_node_by_path_signature(scored_tree, "nonexistent/path")
        assert node is None


class TestOverlayIO:
    def test_write_then_load_roundtrip(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            overlay_path = f.name
        try:
            data = {
                "version": 1,
                "generated_at": "2026-07-10T12:00:00",
                "augmentations": {
                    "n_test": {
                        "path_signature": "test_path",
                        "sentences": [{"script_id": "9999_t1", "script_text": "test"}],
                    }
                },
            }
            write_overlay(overlay_path, data)
            loaded = load_overlay(overlay_path)
            assert loaded["version"] == 1
            assert "n_test" in loaded["augmentations"]
            assert loaded["augmentations"]["n_test"]["sentences"][0]["script_id"] == "9999_t1"
        finally:
            os.unlink(overlay_path)

    def test_load_missing_file_returns_empty(self):
        loaded = load_overlay("/nonexistent/path/overlay.json")
        assert loaded == {}

    def test_write_overlay_appends_to_existing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            overlay_path = f.name
        try:
            data1 = {
                "version": 1,
                "generated_at": "2026-07-10T12:00:00",
                "augmentations": {
                    "n_test": {
                        "path_signature": "test_path",
                        "sentences": [{"script_id": "9999_t1", "script_text": "first"}],
                    }
                },
            }
            write_overlay(overlay_path, data1)

            data2 = {
                "version": 1,
                "generated_at": "2026-07-10T13:00:00",
                "augmentations": {
                    "n_test": {
                        "path_signature": "test_path",
                        "sentences": [{"script_id": "9999_t2", "script_text": "second"}],
                    }
                },
            }
            write_overlay(overlay_path, data2, append=True)
            loaded = load_overlay(overlay_path)
            sentences = loaded["augmentations"]["n_test"]["sentences"]
            assert len(sentences) == 2
            assert sentences[0]["script_id"] == "9999_t1"
            assert sentences[1]["script_id"] == "9999_t2"
        finally:
            os.unlink(overlay_path)


class TestCollectExistingSentenceTexts:
    def test_returns_texts(self):
        node = {
            "sentence_pool": [
                {"script_text": "hello"},
                {"script_text": "world"},
            ]
        }
        texts = collect_existing_sentence_texts(node)
        assert texts == ["hello", "world"]

    def test_empty_pool(self):
        node = {"sentence_pool": []}
        texts = collect_existing_sentence_texts(node)
        assert texts == []

    def test_missing_pool(self):
        node = {}
        texts = collect_existing_sentence_texts(node)
        assert texts == []
