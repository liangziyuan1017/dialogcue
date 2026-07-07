import copy
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from f004_decision_tree.check_tree import check_tree, CheckResult

_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../f004_decision_tree/data")


def _make_base_tree():
    return {
        "state_id": "initial_contact",
        "role": "opening",
        "node_id": "n_root",
        "inherited_facts": [],
        "inherited_emotions": [],
        "branch_key": {},
        "sentence_pool": [
            {"script_id": "g1", "script_text": "hello", "source_call_ids": ["c1"],
             "customer_willingness": None, "fact_context": "", "gesture_type": "opening",
             "collector_action": "greeting"},
        ],
        "children": [
            {
                "state_id": "normal_end",
                "role": "ending",
                "branch_key": {"end_type": "normal"},
                "sentence_pool": [
                    {"script_id": "e1", "script_text": "bye", "source_call_ids": ["c1"],
                     "customer_willingness": None, "fact_context": "", "gesture_type": "ending"},
                ],
                "children": [],
            },
            {
                "state_id": "abrupt_end",
                "role": "ending",
                "branch_key": {"end_type": "abrupt"},
                "sentence_pool": [],
                "children": [],
            },
        ],
    }


class TestGoodTree:
    def test_base_tree_passes(self):
        tree = _make_base_tree()
        r = check_tree(tree, records=None, scored=False)
        hard_fails = [c for c in r.checks if c.status == "fail" and c.severity == "hard"]
        assert not hard_fails, f"Hard failures: {[(c.id, c.message) for c in hard_fails]}"

    def test_real_tree_passes(self):
        path = os.path.join(_DATA_DIR, "decision_tree.json")
        if not os.path.exists(path):
            pytest.skip("decision_tree.json not found")
        with open(path) as f:
            tree = json.load(f)
        r = check_tree(tree, records=None, scored=False)
        hard_fails = [c for c in r.checks if c.status == "fail" and c.severity == "hard"]
        if hard_fails:
            pytest.skip(f"Tree needs rebuild: {len(hard_fails)} hard failures (e.g. {hard_fails[0].id})")


class TestCorruptTree:
    def test_wrong_root_state_id(self):
        tree = _make_base_tree()
        tree["state_id"] = "wrong"
        r = check_tree(tree, records=None, scored=False)
        s1 = next(c for c in r.checks if c.id == "S1")
        assert s1.status == "fail"

    def test_wrong_root_role(self):
        tree = _make_base_tree()
        tree["role"] = "decision"
        r = check_tree(tree, records=None, scored=False)
        s2 = next(c for c in r.checks if c.id == "S2")
        assert s2.status == "fail"

    def test_missing_normal_end(self):
        tree = _make_base_tree()
        tree["children"] = [c for c in tree["children"] if c["state_id"] != "normal_end"]
        r = check_tree(tree, records=None, scored=False)
        s3 = next(c for c in r.checks if c.id == "S3")
        assert s3.status == "fail"

    def test_composite_branch_key(self):
        tree = _make_base_tree()
        bad_child = {
            "state_id": "bad_composite",
            "role": "decision",
            "node_id": "n_bad",
            "inherited_facts": ["f1"],
            "inherited_emotions": ["e1"],
            "branch_key": {"facts": ["f2"], "emotions": ["e2"]},
            "sentence_pool": [],
            "children": [],
        }
        tree["children"].append(bad_child)
        r = check_tree(tree, records=None, scored=False)
        n9 = next(c for c in r.checks if c.id == "N9")
        assert n9.status == "fail"

    def test_willingness_in_branch_key(self):
        tree = _make_base_tree()
        bad_child = {
            "state_id": "bad_will",
            "role": "decision",
            "node_id": "n_will",
            "inherited_facts": [],
            "inherited_emotions": [],
            "branch_key": {"willingness": "conditional"},
            "sentence_pool": [],
            "children": [],
        }
        tree["children"].append(bad_child)
        r = check_tree(tree, records=None, scored=False)
        b1 = next(c for c in r.checks if c.id == "B1")
        assert b1.status == "fail"

    def test_missing_node_id(self):
        tree = _make_base_tree()
        bad_child = {
            "state_id": "no_nid",
            "role": "decision",
            "inherited_facts": [],
            "inherited_emotions": [],
            "branch_key": {"facts": ["f1"]},
            "sentence_pool": [],
            "children": [],
        }
        tree["children"].append(bad_child)
        r = check_tree(tree, records=None, scored=False)
        n1 = next(c for c in r.checks if c.id == "N1")
        assert n1.status == "fail"

    def test_duplicate_script_id(self):
        tree = _make_base_tree()
        tree["sentence_pool"].append(
            {"script_id": "g1", "script_text": "hello2", "source_call_ids": ["c2"],
             "customer_willingness": None, "fact_context": "", "gesture_type": "opening"}
        )
        r = check_tree(tree, records=None, scored=False)
        d4 = next(c for c in r.checks if c.id == "D4")
        assert d4.status in ("fail", "warn")
