import os

from f004_decision_tree.build_decision_tree import (
    _collapse_redundant_facts,
    _load_rewarded,
    _merge_sibling_facts,
    _propagate_facts,
    _split_by_action,
    _split_composite_nodes,
    build_tree,
)


def _sample_record_emotion_cycle(call_id="test-004"):
    return {
        "call_id": call_id,
        "reward": 0,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "我没钱。", "state": {"facts": ["financial_hardship"], "emotions": ["anger"], "willingness": "resistant"}},
            {"turn_index": 2, "role": "催收员", "text": "我理解。", "state": {"action": "empathy"}},
            {"turn_index": 3, "role": "客户", "text": "唉...", "state": {"facts": ["financial_hardship"], "emotions": ["anxiety"], "willingness": "weak"}},
            {"turn_index": 4, "role": "催收员", "text": "别担心。", "state": {"action": "empathy"}},
            {"turn_index": 5, "role": "客户", "text": "我就是气不过！", "state": {"facts": ["financial_hardship"], "emotions": ["anger"], "willingness": "resistant"}},
            {"turn_index": 6, "role": "催收员", "text": "建议还款。", "state": {"action": "plan_proposal"}},
        ],
    }


def _collect_all_sentences(node):
    sentences = list(node.get("sentence_pool", []))
    for child in node.get("children", []):
        sentences.extend(_collect_all_sentences(child))
    return sentences


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


def _check_sorted_tree(node, violations):
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            vals = node["branch_key"][key]
            if vals and vals != sorted(vals):
                violations.append(node.get("state_id"))
    for child in node.get("children", []):
        _check_sorted_tree(child, violations)


def _collect_leaf_and_ids(node, leaf_empty, found_ids):
    for entry in node.get("sentence_pool", []):
        for cid in entry.get("source_call_ids", []):
            found_ids.add(cid)
    children = node.get("children", [])
    if not children:
        if not node.get("sentence_pool"):
            if node.get("state_id") not in ("normal_end", "abrupt_end"):
                leaf_empty.append(node.get("state_id"))
    for child in children:
        _collect_leaf_and_ids(child, leaf_empty, found_ids)


def _branching_histogram(node):
    from collections import Counter
    c = Counter()
    def walk(n):
        kids = n.get("children", [])
        c[len(kids)] += 1
        for k in kids:
            walk(k)
    walk(node)
    return c


def _collect_branch_keys(node, results=None):
    if results is None:
        results = []
    results.append(node.get("branch_key", {}))
    for child in node.get("children", []):
        _collect_branch_keys(child, results)
    return results


def _collect_nodes(node, results=None):
    if results is None:
        results = []
    results.append(node)
    for child in node.get("children", []):
        _collect_nodes(child, results)
    return results


def test_emotion_cycle_same_facts_anger_returns_same_pool():
    rec = _sample_record_emotion_cycle()
    tree = build_tree([rec])
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    anger_nodes = _find_nodes_by_branch_key(tree, {"emotions": ["anger"]})
    assert len(anger_nodes) >= 1, "Should have at least one anger emotion node"


def test_emotion_cycle_anger_and_anxiety_are_siblings():
    rec = _sample_record_emotion_cycle()
    tree = build_tree([rec])
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    anger_nodes = _find_nodes_by_branch_key(tree, {"emotions": ["anger"]})
    anxiety_nodes = _find_nodes_by_branch_key(tree, {"emotions": ["anxiety"]})
    assert len(anger_nodes) >= 1
    assert len(anxiety_nodes) >= 1


def test_emotion_cycle_anger_pool_has_both_sentences():
    rec = _sample_record_emotion_cycle()
    tree = build_tree([rec])
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    all_sentences = _collect_all_sentences(tree)
    texts = [s["script_text"] for s in all_sentences]
    assert any("我理解" in t for t in texts), "First anger response should be in tree"
    assert any("建议还款" in t for t in texts), "Second anger response should be in tree"


def test_real_data_all_criteria():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
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


def test_real_data_opening_gestures():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)
    opening = [s for s in tree["sentence_pool"] if s.get("gesture_type") == "opening"]
    assert len(opening) > 0, "Root should have opening gesture sentences from real data"


def test_real_data_abrupt_end_exists():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)
    abrupt_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "abrupt_end"]
    normal_as_root = [c for c in tree.get("children", []) if c.get("state_id") == "normal_end"]
    assert len(abrupt_as_root) == 1, "Exactly one abrupt_end as root child"
    assert len(normal_as_root) == 1, "Exactly one normal_end as root child"


def test_real_data_leaf_termination():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)
    child_ids = [c.get("state_id") for c in tree.get("children", [])]
    assert "normal_end" in child_ids, "normal_end is root child"
    assert "abrupt_end" in child_ids, "abrupt_end is root child"


def test_real_data_branches_not_chains():
    import importlib.util
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    records = mod.results

    tree = build_tree(records)
    branching = _branching_histogram(tree)
    single_child = branching.get(1, 0)
    total = sum(branching.values())
    ratio = single_child / total if total > 0 else 1
    assert ratio < 0.85, f"Tree is too chain-like: {single_child}/{total} nodes have 1 child ({ratio:.0%})"


def test_no_composite_branch_keys():
    records = _load_rewarded()
    tree = build_tree(records)
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _split_by_action(tree)
    for bk in _collect_branch_keys(tree):
        facts = bk.get("facts", [])
        emotions = bk.get("emotions", [])
        assert not (facts and emotions), f"Composite branch_key with both facts and emotions: {bk}"
        assert len(facts) <= 1, f"Composite branch_key with multiple facts: {bk}"


def test_no_redundant_fact_nodes():
    records = _load_rewarded()
    tree = build_tree(records)
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    for node in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        inf = node.get("inherited_facts", [])
        own_facts = bk.get("facts", [])
        for f in own_facts:
            assert f not in inf, f"Redundant fact node: {node['state_id']} has fact '{f}' already in inherited_facts={inf}"


def test_inherited_facts_strictly_from_parent_chain():
    records = _load_rewarded()
    tree = build_tree(records)
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    for node in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        own_facts = bk.get("facts", [])
        inf = node.get("inherited_facts", [])
        for f in own_facts:
            assert f not in inf, f"Node {node['state_id']}: own fact '{f}' should not be in inherited_facts"


def test_sentences_under_action_nodes_for_fact_emotion_parents():
    records = _load_rewarded()
    tree = build_tree(records)
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])
    for node in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        has_facts = bool(bk.get("facts"))
        has_emotions = bool(bk.get("emotions"))
        if has_facts or has_emotions:
            has_action_sentences = any(
                s.get("collector_action") for s in node.get("sentence_pool", [])
            )
            assert not has_action_sentences, (
                f"Node {node['state_id']} (facts/emotion) has sentences with collector_action "
                f"directly in pool — should be under action child node"
            )
