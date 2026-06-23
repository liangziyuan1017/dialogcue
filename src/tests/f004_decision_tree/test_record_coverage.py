import json
import os

import importlib.util

import pytest


def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_tree():
    tree_path = os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json")
    with open(tree_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _all_tree_sentences(node, results=None):
    if results is None:
        results = []
    for s in node.get("sentence_pool", []):
        results.append(s)
    for c in node.get("children", []):
        _all_tree_sentences(c, results)
    return results


@pytest.fixture(scope="module")
def tree_and_records():
    tree = _load_tree()
    records = _load_rewarded()
    return tree, records


def test_no_composite_branch_keys(tree_and_records):
    tree, _ = tree_and_records
    def find_composite(n, results=[]):
        bk = n.get("branch_key", {})
        facts = bk.get("facts", [])
        emotions = bk.get("emotions", [])
        if len(facts) > 1 or (facts and emotions):
            results.append(n["state_id"])
        for c in n.get("children", []):
            find_composite(c, results)
        return results
    composites = find_composite(tree)
    assert not composites, f"Composite branch keys found: {composites}"


def test_no_redundant_fact_nodes(tree_and_records):
    tree, _ = tree_and_records
    def find_redundant(n, results=[]):
        bk = n.get("branch_key", {})
        inf = n.get("inherited_facts", [])
        for f in bk.get("facts", []):
            if f in inf:
                results.append(f"{n['state_id']}: fact '{f}' in inherited={inf}")
        for c in n.get("children", []):
            find_redundant(c, results)
        return results
    redundant = find_redundant(tree)
    assert not redundant, f"Redundant fact nodes:\n" + "\n".join(redundant)


def test_sentences_under_action_nodes(tree_and_records):
    tree, _ = tree_and_records
    def find_misplaced(n, results=[]):
        bk = n.get("branch_key", {})
        if bk.get("facts") or bk.get("emotions"):
            for s in n.get("sentence_pool", []):
                if s.get("collector_action"):
                    results.append(f"{n['state_id']}: sentence with action '{s['collector_action']}' directly in pool")
        for c in n.get("children", []):
            find_misplaced(c, results)
        return results
    misplaced = find_misplaced(tree)
    assert not misplaced, f"Misplaced sentences:\n" + "\n".join(misplaced)


def test_all_31_call_ids_represented(tree_and_records):
    tree, records = tree_and_records
    all_sents = _all_tree_sentences(tree)
    tree_cids = set()
    for s in all_sents:
        for cid in s.get("source_call_ids", []):
            tree_cids.add(cid)
    data_cids = {r["call_id"] for r in records}
    missing = data_cids - tree_cids
    assert not missing, f"Call IDs in data but not in tree: {missing}"


def test_node_category_correctness(tree_and_records):
    tree, _ = tree_and_records
    errors = []
    def check(n, depth=0):
        bk = n.get("branch_key", {})
        sid = n.get("state_id", "")
        if bk.get("action"):
            if not sid.startswith("a:"):
                errors.append(f"{sid}: has action branch_key but state_id doesn't start with 'a:'")
        if bk.get("facts") and not bk.get("emotions") and not bk.get("action"):
            if not sid.startswith("f:"):
                errors.append(f"{sid}: has facts branch_key but state_id doesn't start with 'f:'")
        if bk.get("emotions") and not bk.get("facts") and not bk.get("action"):
            if not sid.startswith("e:"):
                errors.append(f"{sid}: has emotions branch_key but state_id doesn't start with 'e:'")
        for c in n.get("children", []):
            check(c, depth + 1)
    check(tree)
    assert not errors, "Category errors:\n" + "\n".join(errors)
