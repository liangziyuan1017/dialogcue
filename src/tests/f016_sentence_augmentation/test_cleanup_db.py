import json
import os
from unittest.mock import patch, MagicMock

import pytest

from f016_sentence_augmentation.cleanup_db import (
    build_tree_mappings,
    identify_misplaced_sentences,
    identify_extra_sentences,
    identify_extra_nodes,
)


SCORED_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "../..",
    "f005_context_scoring", "data", "decision_tree_scored.json",
)


def _make_tree():
    return {
        "node_id": "n_root",
        "path_signature": "root",
        "sentence_pool": [
            {"script_id": "2317_t1"},
            {"script_id": "2317_t2"},
        ],
        "children": [
            {
                "node_id": "n_child",
                "path_signature": "root/child",
                "sentence_pool": [{"script_id": "2320_t1"}],
                "children": [],
            }
        ],
    }


class TestBuildTreeMappings:
    def test_builds_script_id_to_path_sig(self):
        tree = _make_tree()
        mappings = build_tree_mappings(tree)
        assert mappings["tree_script_ids"] == {"2317_t1", "2317_t2", "2320_t1"}
        assert mappings["tree_sid_to_psig"]["2317_t1"] == "root"
        assert mappings["tree_sid_to_psig"]["2320_t1"] == "root/child"
        assert mappings["tree_path_signatures"] == {"root", "root/child"}

    def test_real_tree_has_1716_sentences(self):
        with open(SCORED_TREE_PATH, encoding="utf-8") as f:
            tree = json.load(f)
        mappings = build_tree_mappings(tree)
        total = len(mappings["tree_script_ids"])
        assert total == 71, f"Expected 71 tree sentences, got {total}"

    def test_real_tree_has_1395_nodes(self):
        with open(SCORED_TREE_PATH, encoding="utf-8") as f:
            tree = json.load(f)
        mappings = build_tree_mappings(tree)
        total = len(mappings["tree_path_signatures"])
        assert total == 62, f"Expected 62 tree nodes, got {total}"


class TestIdentifyMisplacedSentences:
    def test_identifies_misplaced(self):
        tree_script_ids = {"s1", "s2", "s3"}
        tree_sid_to_psig = {"s1": "path_a", "s2": "path_b", "s3": "path_c"}
        tree_path_signatures = {"path_a", "path_b", "path_c"}
        db_psig_to_node_id = {"path_a": 1, "path_b": 2, "path_c": 3, "old_path": 4}
        db_sid_to_node_psig = {
            "s1": "old_path",
            "s2": "path_b",
            "s3": "path_c",
            "s_extra": "old_path",
        }
        misplaced = identify_misplaced_sentences(
            tree_script_ids, tree_sid_to_psig, tree_path_signatures,
            db_psig_to_node_id, db_sid_to_node_psig,
        )
        assert "s1" in misplaced
        assert misplaced["s1"]["correct_psig"] == "path_a"
        assert misplaced["s1"]["correct_node_id"] == 1
        assert "s2" not in misplaced

    def test_no_misplaced(self):
        tree_script_ids = {"s1", "s2"}
        tree_sid_to_psig = {"s1": "path_a", "s2": "path_b"}
        tree_path_signatures = {"path_a", "path_b"}
        db_psig_to_node_id = {"path_a": 1, "path_b": 2}
        db_sid_to_node_psig = {"s1": "path_a", "s2": "path_b"}
        misplaced = identify_misplaced_sentences(
            tree_script_ids, tree_sid_to_psig, tree_path_signatures,
            db_psig_to_node_id, db_sid_to_node_psig,
        )
        assert misplaced == {}


class TestIdentifyExtraSentences:
    def test_identifies_extras(self):
        tree_script_ids = {"s1", "s2"}
        db_script_ids = {"s1", "s2", "s_extra1", "s_extra2", "9999_aug1"}
        extras = identify_extra_sentences(tree_script_ids, db_script_ids, keep_augmented=True)
        assert "s_extra1" in extras
        assert "s_extra2" in extras
        assert "9999_aug1" not in extras

    def test_deletes_augmented_when_not_kept(self):
        tree_script_ids = {"s1"}
        db_script_ids = {"s1", "9999_aug1"}
        extras = identify_extra_sentences(tree_script_ids, db_script_ids, keep_augmented=False)
        assert "9999_aug1" in extras


class TestIdentifyExtraNodes:
    def test_identifies_extras(self):
        tree_path_signatures = {"path_a", "path_b"}
        db_path_signatures = {"path_a", "path_b", "old_path1", "old_path2"}
        extras = identify_extra_nodes(tree_path_signatures, db_path_signatures)
        assert extras == {"old_path1", "old_path2"}

    def test_no_extras(self):
        tree_path_signatures = {"path_a", "path_b"}
        db_path_signatures = {"path_a", "path_b"}
        extras = identify_extra_nodes(tree_path_signatures, db_path_signatures)
        assert extras == set()
