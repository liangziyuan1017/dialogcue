import json
import os

from f004_decision_tree.build_decision_tree import build_tree, write_decision_tree
from f004_decision_tree.tree_transforms import _split_by_action


VALID_ROLES = {"opening", "ending", "decision", "action"}


def _sample_record_with_greeting_and_closing(call_id="rg-001"):
    return {
        "call_id": call_id,
        "reward": 1,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好，请问是张女士吗？", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "对。", "state": {"willingness": "cooperative"}},
            {"turn_index": 2, "role": "催收员", "text": "女士，我帮您申请减免。", "state": {"action": "plan_proposal"}},
            {"turn_index": 3, "role": "客户", "text": "好的，我同意。", "state": {"willingness": "cooperative"}},
            {"turn_index": 4, "role": "催收员", "text": "好的，请尽快还款。", "state": {"action": "closure"}},
            {"turn_index": 5, "role": "催收员", "text": "祝您生活愉快，再见。", "state": {"action": "goodbye"}},
        ],
    }


def _sample_record_with_facts(call_id="rg-002"):
    return {
        "call_id": call_id,
        "reward": 0,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "我没钱。", "state": {"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "resistant"}},
            {"turn_index": 2, "role": "催收员", "text": "我理解您的困难。", "state": {"action": "empathy"}},
            {"turn_index": 3, "role": "客户", "text": "嗯。", "state": {"facts": ["financial_hardship"], "willingness": "weak"}},
            {"turn_index": 4, "role": "催收员", "text": "建议您还最低还款。", "state": {"action": "plan_proposal"}},
        ],
    }


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


def _find_node(node, state_id):
    if node.get("state_id") == state_id:
        return node
    for child in node.get("children", []):
        r = _find_node(child, state_id)
        if r is not None:
            return r
    return None


def test_every_node_has_valid_role():
    records = [_sample_record_with_greeting_and_closing("call-A"), _sample_record_with_facts("call-B")]
    out = "/tmp/test_role_tagging_tree.json"
    write_decision_tree(records, out)
    with open(out) as f:
        tree = json.load(f)
    os.unlink(out)
    for node in _all_nodes(tree):
        assert node.get("role") in VALID_ROLES, f"Node {node.get('state_id')} has invalid role {node.get('role')}"


def test_root_role_is_opening():
    records = [_sample_record_with_greeting_and_closing()]
    out = "/tmp/test_role_tagging_root.json"
    write_decision_tree(records, out)
    with open(out) as f:
        tree = json.load(f)
    os.unlink(out)
    assert tree.get("role") == "opening", f"Root role should be 'opening', got {tree.get('role')}"


def test_end_nodes_role_is_ending():
    records = [_sample_record_with_greeting_and_closing()]
    out = "/tmp/test_role_tagging_end.json"
    write_decision_tree(records, out)
    with open(out) as f:
        tree = json.load(f)
    os.unlink(out)
    ne = _find_node(tree, "normal_end")
    ae = _find_node(tree, "abrupt_end")
    assert ne is not None and ne.get("role") == "ending"
    assert ae is not None and ae.get("role") == "ending"


def test_split_by_action_skips_non_decision_nodes():
    root = {
        "state_id": "initial_contact",
        "role": "opening",
        "branch_key": {},
        "sentence_pool": [
            {"script_text": "您好。", "script_id": "s1", "source_call_ids": ["c1"], "collector_action": "greeting"},
            {"script_text": "请问是张女士吗？", "script_id": "s2", "source_call_ids": ["c1"], "collector_action": "greeting"},
            {"script_text": "请尽快还款。", "script_id": "s3", "source_call_ids": ["c1"], "collector_action": "closure"},
        ],
        "children": [],
    }
    _split_by_action(root)
    assert len(root["sentence_pool"]) == 3, "Root (role=opening) must not be action-split"
    assert len(root["children"]) == 0, "Root must not gain action children"


def test_greetings_stay_in_root_after_write():
    records = [_sample_record_with_greeting_and_closing("call-g1"), _sample_record_with_facts("call-g2")]
    out = "/tmp/test_role_tagging_greetings.json"
    write_decision_tree(records, out)
    with open(out) as f:
        tree = json.load(f)
    os.unlink(out)
    opening_in_root = [s for s in tree["sentence_pool"] if s.get("gesture_type") == "opening"]
    assert len(opening_in_root) >= 2, f"Root should retain opening greetings, found {len(opening_in_root)}"
    child_ids = [c.get("state_id") for c in tree.get("children", [])]
    assert "a:greeting" not in child_ids, "Root must not have an a:greeting action child"


def test_endings_consolidated_in_normal_end_after_write():
    records = [_sample_record_with_greeting_and_closing("call-e1"), _sample_record_with_facts("call-e2")]
    out = "/tmp/test_role_tagging_endings.json"
    write_decision_tree(records, out)
    with open(out) as f:
        tree = json.load(f)
    os.unlink(out)
    ne = _find_node(tree, "normal_end")
    assert ne is not None
    ending_in_normal = [s for s in ne["sentence_pool"] if s.get("gesture_type") == "ending"]
    assert len(ending_in_normal) >= 2, f"normal_end should hold ending sentences, found {len(ending_in_normal)}"
    for node in _all_nodes(tree):
        if node.get("state_id") in ("normal_end", "abrupt_end"):
            continue
        for s in node.get("sentence_pool", []):
            if s.get("script_text") not in ("[对话未正常结束]", "[正常结束]"):
                assert s.get("gesture_type") != "ending", (
                    f"Ending sentence leaked into {node.get('state_id')}: {s.get('script_text')}"
                )
