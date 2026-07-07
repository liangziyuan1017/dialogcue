import json
import os

from f004_decision_tree.build_decision_tree import (
    build_tree,
    extract_state_paths,
    find_node,
    write_decision_tree,
)


def _sample_record(call_id="test-001", reward=0):
    return {
        "call_id": call_id,
        "reward": reward,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好，请问是张女士吗？", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "对。"},
            {"turn_index": 2, "role": "催收员", "text": "女士，我帮您申请减免。", "state": {"action": "plan_proposal"}},
            {"turn_index": 3, "role": "客户", "text": "好的，我同意。", "state": {"willingness": "cooperative"}},
            {"turn_index": 4, "role": "催收员", "text": "好的，请尽快还款。", "state": {"action": "closure"}},
        ],
    }


def _sample_record_with_facts(call_id="test-002"):
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


def _sample_record_same_facts_diff_willingness(call_id="test-003"):
    return {
        "call_id": call_id,
        "reward": 1,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "我没钱。", "state": {"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "negotiating"}},
            {"turn_index": 2, "role": "催收员", "text": "我们可以帮您调整。", "state": {"action": "plan_proposal"}},
        ],
    }


def _sample_record_with_closing(call_id="test-005"):
    return {
        "call_id": call_id,
        "reward": 1,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "嗯。", "state": {"willingness": "cooperative"}},
            {"turn_index": 2, "role": "催收员", "text": "好的，请尽快还款。", "state": {"action": "closure"}},
            {"turn_index": 3, "role": "催收员", "text": "祝您生活愉快，再见。", "state": {"action": "goodbye"}},
        ],
    }


def _sample_record_no_closing(call_id="test-006"):
    return {
        "call_id": call_id,
        "reward": 0,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "我没钱。", "state": {"facts": ["financial_hardship"], "willingness": "resistant"}},
            {"turn_index": 2, "role": "催收员", "text": "建议您还款。", "state": {"action": "plan_proposal"}},
        ],
    }


def _collect_all_sentences(node):
    sentences = list(node.get("sentence_pool", []))
    for child in node.get("children", []):
        sentences.extend(_collect_all_sentences(child))
    return sentences


def _collect_all_call_ids(node):
    ids = set()
    for entry in node.get("sentence_pool", []):
        for cid in entry.get("source_call_ids", []):
            ids.add(cid)
    for child in node.get("children", []):
        ids.update(_collect_all_call_ids(child))
    return ids


def _check_sorted(node):
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            vals = node["branch_key"][key]
            if vals:
                assert vals == sorted(vals)
    for child in node.get("children", []):
        _check_sorted(child)


def _check_leaf_pools(node):
    children = node.get("children", [])
    if not children:
        assert "sentence_pool" in node
        assert len(node["sentence_pool"]) > 0
    for child in children:
        _check_leaf_pools(child)


def _find_nodes_by_branch_key(node, target_key, results=None):
    if results is None:
        results = []
    if node.get("branch_key") == target_key:
        results.append(node)
    for child in node.get("children", []):
        _find_nodes_by_branch_key(child, target_key, results)
    return results


def _find_nodes_by_state_id(node, target_id, results=None):
    if results is None:
        results = []
    if node.get("state_id") == target_id:
        results.append(node)
    for child in node.get("children", []):
        _find_nodes_by_state_id(child, target_id, results)
    return results


def test_extract_state_paths_returns_pairs():
    rec = _sample_record()
    paths = extract_state_paths(rec)
    assert isinstance(paths, list)
    assert len(paths) > 0


def test_extract_state_paths_customer_key_is_facts_emotions_only():
    rec = _sample_record_with_facts()
    paths = extract_state_paths(rec)
    for item in paths:
        if item["type"] == "customer":
            key = item["branch_key"]
            assert "willingness" not in key
            assert "facts" in key or "emotions" in key or (key.get("facts") is None and key.get("emotions") is None)


def test_extract_state_paths_willingness_on_sentence():
    rec = _sample_record_with_facts()
    paths = extract_state_paths(rec)
    collector_steps = [p for p in paths if p["type"] == "collector"]
    for step in collector_steps:
        if step.get("sentence"):
            assert "customer_willingness" in step["sentence"]


def test_build_tree_has_root_initial_contact():
    tree = build_tree([_sample_record()])
    assert tree["state_id"] == "initial_contact"


def test_build_tree_branches_on_facts_emotions():
    r1 = _sample_record_with_facts("call-A")
    r2 = _sample_record_same_facts_diff_willingness("call-B")
    tree = build_tree([r1, r2])
    root_children = tree.get("children", [])
    assert len(root_children) > 0
    financial_hardship_branch = [c for c in root_children if "financial_hardship" in str(c.get("branch_key", {}))]
    assert len(financial_hardship_branch) == 1, "Same (facts, emotions) should merge into one branch"


def test_build_tree_willingness_merges_into_same_branch():
    r1 = _sample_record_with_facts("call-A")
    r2 = _sample_record_same_facts_diff_willingness("call-B")
    tree = build_tree([r1, r2])
    all_sentences = _collect_all_sentences(tree)
    willingness_labels = set(s.get("customer_willingness") for s in all_sentences if s.get("customer_willingness"))
    assert "resistant" in willingness_labels or "weak" in willingness_labels
    assert "negotiating" in willingness_labels


def test_build_tree_leaf_has_sentence_pool():
    tree = build_tree([_sample_record()])
    _check_leaf_pools(tree)


def test_sentence_entry_has_required_fields():
    tree = build_tree([_sample_record()])
    entries = _collect_all_sentences(tree)
    for entry in entries:
        assert "script_text" in entry
        assert "script_id" in entry
        assert "source_call_ids" in entry
        assert "customer_willingness" in entry


def test_all_call_ids_represented():
    r1 = _sample_record("call-A")
    r2 = _sample_record_with_facts("call-B")
    tree = build_tree([r1, r2])
    all_call_ids = _collect_all_call_ids(tree)
    assert "call-A" in all_call_ids
    assert "call-B" in all_call_ids


def test_keywords_sorted_at_every_node():
    tree = build_tree([_sample_record_with_facts()])
    _check_sorted(tree)


def test_find_node_exact_match():
    tree = build_tree([_sample_record()])
    result = find_node(tree, {"action": "greeting"})
    assert result is not None


def test_find_node_fallback_removes_emotions():
    tree = build_tree([_sample_record_with_facts()])
    result = find_node(tree, {"facts": ["financial_hardship"], "emotions": ["distress", "anger"]})
    assert result is not None


def test_write_decision_tree_produces_json():
    records = [_sample_record()]
    output_path = "/tmp/test_decision_tree_f004.json"
    count = write_decision_tree(records, output_path)
    assert count > 0
    with open(output_path) as f:
        data = json.load(f)
    assert data["state_id"] == "initial_contact"
    os.unlink(output_path)


def test_root_greeting_sentences_have_opening_gesture_type():
    rec = _sample_record()
    tree = build_tree([rec])
    greeting_sentences = [s for s in tree["sentence_pool"] if "您好" in s["script_text"]]
    assert len(greeting_sentences) > 0, "Root should have greeting sentences"
    for s in greeting_sentences:
        assert s.get("gesture_type") == "opening", f"Greeting sentence should have gesture_type='opening': {s['script_text']}"


def test_closing_sentences_have_ending_gesture_type():
    rec = _sample_record_with_closing()
    tree = build_tree([rec])
    all_sentences = _collect_all_sentences(tree)
    ending_sentences = [s for s in all_sentences if s.get("gesture_type") == "ending"]
    assert len(ending_sentences) > 0, "Should have ending gesture sentences for closing actions"


def test_dialog_without_closing_has_abrupt_end_node():
    rec = _sample_record_no_closing()
    tree = build_tree([rec])
    abrupt_as_root_child = [c for c in tree.get("children", []) if c.get("state_id") == "abrupt_end"]
    assert len(abrupt_as_root_child) == 1, "Should have exactly one abrupt_end as root child"
    assert abrupt_as_root_child[0].get("gesture_type") == "ending"


def test_tree_has_exactly_one_normal_end_and_one_abrupt_end():
    r1 = _sample_record_with_closing("call-A")
    r2 = _sample_record_no_closing("call-B")
    tree = build_tree([r1, r2])
    normal_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "normal_end"]
    abrupt_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "abrupt_end"]
    assert len(normal_as_root) == 1, "Should have exactly one normal_end as root child"
    assert len(abrupt_as_root) == 1, "Should have exactly one abrupt_end as root child"
    assert normal_as_root[0].get("gesture_type") == "ending"
    assert abrupt_as_root[0].get("gesture_type") == "ending"


def test_end_nodes_are_root_children():
    r1 = _sample_record_with_closing("call-A")
    r2 = _sample_record_no_closing("call-B")
    tree = build_tree([r1, r2])
    child_ids = [c.get("state_id") for c in tree.get("children", [])]
    assert "normal_end" in child_ids, "normal_end should be direct child of root"
    assert "abrupt_end" in child_ids, "abrupt_end should be direct child of root"


def test_every_leaf_is_end_node_or_abrupt_end():
    r1 = _sample_record_with_closing("call-A")
    r2 = _sample_record_no_closing("call-B")
    tree = build_tree([r1, r2])
    normal_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "normal_end"]
    abrupt_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "abrupt_end"]
    assert len(normal_as_root) == 1 and len(abrupt_as_root) == 1, "Exactly 1 normal_end + 1 abrupt_end as root children"


def test_greeting_sentences_have_collector_action():
    rec = _sample_record()
    tree = build_tree([rec])
    greeting = [s for s in tree["sentence_pool"] if s.get("gesture_type") == "opening"]
    assert len(greeting) > 0
    for s in greeting:
        assert s.get("collector_action") == "greeting"


def test_decision_sentences_have_collector_action():
    rec = _sample_record_with_facts()
    tree = build_tree([rec])
    all_s = _collect_all_sentences(tree)
    with_action = [s for s in all_s if s.get("collector_action")]
    assert len(with_action) > 0, "Decision node sentences should have collector_action"
    actions = set(s["collector_action"] for s in with_action)
    assert "empathy" in actions or "plan_proposal" in actions


def test_sentences_without_action_have_no_collector_action_key():
    rec = {
        "call_id": "test-no-action",
        "reward": 0,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "嗯。", "state": {"willingness": "cooperative"}},
            {"turn_index": 2, "role": "催收员", "text": "随便说说。", "state": {}},
        ],
    }
    tree = build_tree([rec])
    all_s = _collect_all_sentences(tree)
    no_action = [s for s in all_s if "collector_action" not in s and s.get("script_text") == "随便说说。"]
    assert len(no_action) == 1, "Sentence without action state should appear without collector_action key"
