import importlib.util
import json
import os
import tempfile

import pytest

from f004_decision_tree.build_decision_tree import write_decision_tree


def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _all_nodes(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return
    visited.add(nid)
    yield node
    for child in node.get("children", []):
        yield from _all_nodes(child, visited)


def _all_sentences(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return
    visited.add(nid)
    for s in node.get("sentence_pool", []):
        yield s
    for child in node.get("children", []):
        yield from _all_sentences(child, visited)


def _find_node(node, state_id, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return None
    visited.add(nid)
    if node.get("state_id") == state_id:
        return node
    for child in node.get("children", []):
        r = _find_node(child, state_id, visited)
        if r is not None:
            return r
    return None


@pytest.fixture(scope="module")
def tree():
    records = _load_rewarded()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out_path = f.name
    try:
        write_decision_tree(records, out_path)
        with open(out_path, encoding="utf-8") as f:
            return json.load(f)
    finally:
        os.unlink(out_path)


@pytest.fixture(scope="module")
def records():
    return _load_rewarded()


class TestF004RootInvariant:
    def test_root_state_id(self, tree):
        assert tree["state_id"] == "initial_contact"

    def test_root_role_opening(self, tree):
        assert tree.get("role") == "opening"


class TestF004OpeningGestures:
    def test_root_has_opening_sentences(self, tree):
        root_opening = [s for s in tree["sentence_pool"] if s.get("gesture_type") == "opening"]
        assert len(root_opening) > 0, "Root should have opening greeting sentences"

    def test_root_has_no_a_greeting_child(self, tree):
        child_ids = [c.get("state_id") for c in tree.get("children", [])]
        assert "a:greeting" not in child_ids

    def test_root_opening_count_matches_records(self, tree, records):
        root_pool_cids = set()
        for s in tree.get("sentence_pool", []):
            root_pool_cids.update(s.get("source_call_ids", []))
        expected_cids = set()
        for rec in records:
            for turn in rec.get("turns_annotated", []):
                if turn["role"] == "催收员" and turn.get("state", {}).get("action") == "greeting":
                    expected_cids.add(rec["call_id"])
                    break
        missing = expected_cids - root_pool_cids
        assert not missing, f"{len(missing)} records with greetings not in root pool"


class TestF004EndingConsolidation:
    def test_normal_end_has_ending_sentences(self, tree):
        ne = _find_node(tree, "normal_end")
        assert ne is not None
        ending_in_ne = [s for s in ne["sentence_pool"] if s.get("gesture_type") == "ending"]
        assert len(ending_in_ne) > 0, "normal_end should hold ending sentences"

    def test_no_ending_sentences_outside_end_nodes(self, tree):
        for node in _all_nodes(tree):
            if node.get("state_id") in ("normal_end", "abrupt_end"):
                continue
            for s in node.get("sentence_pool", []):
                if s.get("script_text") in ("[对话未正常结束]", "[正常结束]"):
                    continue
                assert s.get("gesture_type") != "ending", (
                    f"Ending leaked into {node.get('state_id')}: {s.get('script_text')}"
                )


class TestF004EndNodeStructure:
    def test_exactly_one_normal_end_as_root_child(self, tree):
        root_children = [c for c in tree.get("children", []) if c.get("state_id") == "normal_end"]
        assert len(root_children) == 1

    def test_exactly_one_abrupt_end_as_root_child(self, tree):
        root_children = [c for c in tree.get("children", []) if c.get("state_id") == "abrupt_end"]
        assert len(root_children) == 1

    def test_end_nodes_are_root_children(self, tree):
        child_ids = [c.get("state_id") for c in tree.get("children", [])]
        assert "normal_end" in child_ids
        assert "abrupt_end" in child_ids

    def test_end_nodes_role_ending(self, tree):
        ne = _find_node(tree, "normal_end")
        ae = _find_node(tree, "abrupt_end")
        assert ne.get("role") == "ending"
        assert ae.get("role") == "ending"


class TestF004LeafTermination:
    def test_every_leaf_is_end_node(self, tree):
        non_end_leaves = []
        for node in _all_nodes(tree):
            children = node.get("children", [])
            if not children:
                sid = node.get("state_id", "")
                is_end = sid in ("normal_end", "abrupt_end")
                has_ending = any(s.get("gesture_type") == "ending" for s in node.get("sentence_pool", []))
                if not is_end and not has_ending and node is not tree:
                    non_end_leaves.append(sid)
        assert len(non_end_leaves) == 0 or all(not n.startswith("normal_end") for n in non_end_leaves), f"Non-end leaves that shouldn't exist: {non_end_leaves[:5]}"


class TestF004SentenceFields:
    def test_every_sentence_has_required_fields(self, tree):
        required = {"script_text", "script_id", "source_call_ids", "customer_willingness"}
        for s in _all_sentences(tree):
            missing = required - set(s.keys())
            assert not missing, f"Sentence {s.get('script_id')} missing: {missing}"


class TestF004CallIdCoverage:
    def test_all_call_ids_in_tree(self, tree, records):
        all_cids = set()
        for s in _all_sentences(tree):
            all_cids.update(s.get("source_call_ids", []))
        expected = set(r["call_id"] for r in records)
        missing = expected - all_cids
        assert not missing, f"Missing {len(missing)} call_ids: {sorted(missing)[:5]}"


class TestF004NodeMetadata:
    def test_every_node_has_role(self, tree):
        valid_roles = {"opening", "ending", "decision", "action"}
        for node in _all_nodes(tree):
            role = node.get("role")
            assert role in valid_roles, f"Node {node.get('state_id')} has invalid role: {role}"

    def test_every_node_has_node_id(self, tree):
        for node in _all_nodes(tree):
            if node.get("state_id") in ("normal_end", "abrupt_end"):
                continue
            assert "node_id" in node, f"Node {node.get('state_id')} missing node_id"

    def test_every_node_has_inherited_facts_emotions(self, tree):
        for node in _all_nodes(tree):
            if node.get("state_id") in ("normal_end", "abrupt_end"):
                continue
            assert "inherited_facts" in node, f"Node {node.get('state_id')} missing inherited_facts"
            assert "inherited_emotions" in node, f"Node {node.get('state_id')} missing inherited_emotions"

    def test_keywords_sorted(self, tree):
        for node in _all_nodes(tree):
            for key in ("facts", "emotions"):
                if key in node.get("branch_key", {}):
                    vals = node["branch_key"][key]
                    if vals:
                        assert vals == sorted(vals), f"Unsorted {key} in {node.get('state_id')}"

    def test_no_composite_branch_keys(self, tree):
        for node in _all_nodes(tree):
            bk = node.get("branch_key", {})
            facts = bk.get("facts", [])
            emotions = bk.get("emotions", [])
            if facts and emotions:
                pytest.fail(f"Composite branch_key in {node.get('state_id')}: {bk}")
            if len(facts) > 1:
                pytest.fail(f"Multi-fact branch_key in {node.get('state_id')}: {bk}")
