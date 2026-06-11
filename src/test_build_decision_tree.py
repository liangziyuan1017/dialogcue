import json
import os

from src.build_decision_tree import (
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


def _check_leaf_pools(node):
    children = node.get("children", [])
    if not children:
        assert "sentence_pool" in node
        assert len(node["sentence_pool"]) > 0
    for child in children:
        _check_leaf_pools(child)


def test_sentence_entry_has_required_fields():
    tree = build_tree([_sample_record()])
    entries = _collect_all_sentences(tree)
    for entry in entries:
        assert "script_text" in entry
        assert "script_id" in entry
        assert "source_call_ids" in entry
        assert "customer_willingness" in entry


def _collect_all_sentences(node):
    sentences = list(node.get("sentence_pool", []))
    for child in node.get("children", []):
        sentences.extend(_collect_all_sentences(child))
    return sentences


def test_all_call_ids_represented():
    r1 = _sample_record("call-A")
    r2 = _sample_record_with_facts("call-B")
    tree = build_tree([r1, r2])
    all_call_ids = _collect_all_call_ids(tree)
    assert "call-A" in all_call_ids
    assert "call-B" in all_call_ids


def _collect_all_call_ids(node):
    ids = set()
    for entry in node.get("sentence_pool", []):
        for cid in entry.get("source_call_ids", []):
            ids.add(cid)
    for child in node.get("children", []):
        ids.update(_collect_all_call_ids(child))
    return ids


def test_keywords_sorted_at_every_node():
    tree = build_tree([_sample_record_with_facts()])
    _check_sorted(tree)


def _check_sorted(node):
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            vals = node["branch_key"][key]
            if vals:
                assert vals == sorted(vals)
    for child in node.get("children", []):
        _check_sorted(child)


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


def test_real_data_all_criteria():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)

    assert tree["state_id"] == "initial_contact"

    leaf_empty = []
    found_ids = set()
    _collect_leaf_and_ids(tree, leaf_empty, found_ids)
    assert len(leaf_empty) == 0, f"{len(leaf_empty)} leaf nodes with empty sentence_pool"

    all_call_ids = set(r["call_id"] for r in records)
    missing = all_call_ids - found_ids
    assert len(missing) == 0, f"Missing {len(missing)} call_ids"

    violations = []
    _check_sorted_tree(tree, violations)
    assert len(violations) == 0

    all_sentences = _collect_all_sentences(tree)
    for s in all_sentences:
        assert "customer_willingness" in s, f"Sentence missing customer_willingness: {s.get('script_id')}"


def test_real_data_branches_not_chains():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)
    branching = _branching_histogram(tree)
    single_child = branching.get(1, 0)
    total = sum(branching.values())
    ratio = single_child / total if total > 0 else 1
    assert ratio < 0.8, f"Tree is too chain-like: {single_child}/{total} nodes have 1 child ({ratio:.0%})"


def _branching_histogram(node):
    from collections import Counter
    c = Counter()
    def walk(n):
        kids = n.get("children", [])
        c[len(kids)] += 1
        for k in kids: walk(k)
    walk(node)
    return c


def _collect_leaf_and_ids(node, leaf_empty, found_ids):
    for entry in node.get("sentence_pool", []):
        for cid in entry.get("source_call_ids", []):
            found_ids.add(cid)
    children = node.get("children", [])
    if not children:
        if not node.get("sentence_pool"):
            leaf_empty.append(node.get("state_id"))
    for child in children:
        _collect_leaf_and_ids(child, leaf_empty, found_ids)


def _check_sorted_tree(node, violations):
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            vals = node["branch_key"][key]
            if vals and vals != sorted(vals):
                violations.append(node.get("state_id"))
    for child in node.get("children", []):
        _check_sorted_tree(child, violations)
