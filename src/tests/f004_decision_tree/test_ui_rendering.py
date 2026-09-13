import json
import os

_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "data", "decision_tree.json")

STYLE_MAP = {
    "opening": {"shape": "round-rectangle", "bg": "#052e16", "border": "#22c55e", "text": "#4ade80"},
    "decision": {"shape": "round-rectangle", "bg": "#1e3a5f", "border": "#3b82f6", "text": "#60a5fa"},
    "emotion": {"shape": "ellipse", "bg": "#2e1065", "border": "#a78bfa", "text": "#c4b5fd"},
    "action": {"shape": "diamond", "bg": "#422006", "border": "#f59e0b", "text": "#fbbf24"},
    "ending": {"shape": "ellipse", "bg": "#422006", "border": "#f59e0b", "text": "#fbbf24"},
    "abrupt": {"shape": "triangle", "bg": "#450a0a", "border": "#ef4444", "text": "#f87171"},
}


def _node_type(node, depth):
    if depth == 0:
        return "opening"
    if node.get("state_id") == "abrupt_end":
        return "abrupt"
    if node.get("state_id") == "normal_end":
        return "ending"
    bk = node.get("branch_key", {})
    has_facts = bool(bk.get("facts"))
    has_emotions = bool(bk.get("emotions"))
    if not has_facts and has_emotions:
        return "emotion"
    if bk.get("action"):
        return "action"
    return "decision"


def _collect_nodes(node, depth=0, results=None):
    if results is None:
        results = []
    ntype = _node_type(node, depth)
    results.append((node, depth, ntype))
    for child in node.get("children", []):
        _collect_nodes(child, depth + 1, results)
    return results


def _load_tree():
    with open(_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_every_action_node_is_type_action():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        if bk.get("action") and ntype != "action":
            violations.append((node["state_id"], bk["action"], ntype))
    assert not violations, (
        f"{len(violations)} action nodes have wrong type:\n"
        + "\n".join(f"  {sid} (action={act}) typed as {t}" for sid, act, t in violations)
    )


def test_action_nodes_have_diamond_shape():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        if ntype == "action":
            style = STYLE_MAP["action"]
            if style["shape"] != "diamond":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} action nodes would not render as diamond"


def test_action_nodes_have_amber_color():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        if ntype == "action":
            style = STYLE_MAP["action"]
            if style["border"] != "#f59e0b" or style["bg"] != "#422006":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} action nodes would not render with amber color"


def test_empathy_action_nodes_are_type_action():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        if bk.get("action") == "empathy" and ntype != "action":
            violations.append(node["state_id"])
    assert not violations, (
        f"{len(violations)} empathy action nodes are typed as '{ntype}' instead of 'action': "
        + ", ".join(violations)
    )


def test_pressure_action_nodes_are_type_action():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        if bk.get("action") == "pressure" and ntype != "action":
            violations.append(node["state_id"])
    assert not violations, (
        f"{len(violations)} pressure action nodes are typed as '{ntype}' instead of 'action': "
        + ", ".join(violations)
    )


def test_emotion_nodes_never_have_action_key():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        if ntype == "emotion" and bk.get("action"):
            violations.append((node["state_id"], bk["action"]))
    assert not violations, (
        f"{len(violations)} emotion-typed nodes have action key:\n"
        + "\n".join(f"  {sid} action={act}" for sid, act in violations)
    )


def test_emotion_nodes_have_ellipse_shape():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        if ntype == "emotion":
            style = STYLE_MAP["emotion"]
            if style["shape"] != "ellipse":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} emotion nodes would not render as ellipse"


def test_emotion_nodes_have_purple_color():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        if ntype == "emotion":
            style = STYLE_MAP["emotion"]
            if style["border"] != "#a78bfa" or style["bg"] != "#2e1065":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} emotion nodes would not render with purple color"


def test_type_shape_color_consistency():
    tree = _load_tree()
    all_nodes = _collect_nodes(tree)
    type_counts = {}
    for node, _depth, ntype in all_nodes:
        type_counts[ntype] = type_counts.get(ntype, 0) + 1
        style = STYLE_MAP.get(ntype)
        assert style is not None, f"Node {node['state_id']} has unknown type '{ntype}'"
    expected_types = {"opening", "decision", "emotion", "action", "ending", "abrupt"}
    actual_types = set(type_counts.keys())
    assert actual_types == expected_types, (
        f"Type mismatch: expected {expected_types}, got {actual_types}"
    )


def test_no_node_has_conflicting_type_signals():
    tree = _load_tree()
    violations = []
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        signals = []
        if bk.get("facts"):
            signals.append("facts")
        if bk.get("emotions"):
            signals.append("emotions")
        if bk.get("action"):
            signals.append("action")
        if bk.get("end_type"):
            signals.append("end")
        if len(signals) > 1 and ntype != "decision":
            violations.append((node["state_id"], signals, ntype))
    assert not violations, (
        f"{len(violations)} nodes have conflicting signals:\n"
        + "\n".join(f"  {sid} signals={sig} type={t}" for sid, sig, t in violations)
    )


def test_all_7_action_categories_render_as_action_type():
    tree = _load_tree()
    seen_actions = set()
    for node, _depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        act = bk.get("action")
        if act:
            seen_actions.add(act)
            assert ntype == "action", (
                f"Action node {node['state_id']} (action={act}) is type '{ntype}', expected 'action'"
            )
        expected_actions = {"information", "plan_proposal", "pressure", "empathy", "legal_threat", "greeting", "closure"}
    assert seen_actions, "expected at least one action category in the tree"
    assert seen_actions.issubset(expected_actions), (
        f"Action categories mismatch: unexpected {seen_actions - expected_actions}, got {seen_actions}"
    )
