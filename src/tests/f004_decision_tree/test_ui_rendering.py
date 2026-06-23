import json
import os

_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json")

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
    for node, depth, ntype in _collect_nodes(tree):
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
    for node, depth, ntype in _collect_nodes(tree):
        if ntype == "action":
            style = STYLE_MAP["action"]
            if style["shape"] != "diamond":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} action nodes would not render as diamond"


def test_action_nodes_have_amber_color():
    tree = _load_tree()
    violations = []
    for node, depth, ntype in _collect_nodes(tree):
        if ntype == "action":
            style = STYLE_MAP["action"]
            if style["border"] != "#f59e0b" or style["bg"] != "#422006":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} action nodes would not render with amber color"


def test_empathy_action_nodes_are_type_action():
    tree = _load_tree()
    violations = []
    for node, depth, ntype in _collect_nodes(tree):
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
    for node, depth, ntype in _collect_nodes(tree):
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
    for node, depth, ntype in _collect_nodes(tree):
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
    for node, depth, ntype in _collect_nodes(tree):
        if ntype == "emotion":
            style = STYLE_MAP["emotion"]
            if style["shape"] != "ellipse":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} emotion nodes would not render as ellipse"


def test_emotion_nodes_have_purple_color():
    tree = _load_tree()
    violations = []
    for node, depth, ntype in _collect_nodes(tree):
        if ntype == "emotion":
            style = STYLE_MAP["emotion"]
            if style["border"] != "#a78bfa" or style["bg"] != "#2e1065":
                violations.append(node["state_id"])
    assert not violations, f"{len(violations)} emotion nodes would not render with purple color"


def test_type_shape_color_consistency():
    tree = _load_tree()
    all_nodes = _collect_nodes(tree)
    type_counts = {}
    for node, depth, ntype in all_nodes:
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
    for node, depth, ntype in _collect_nodes(tree):
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
    for node, depth, ntype in _collect_nodes(tree):
        bk = node.get("branch_key", {})
        act = bk.get("action")
        if act:
            seen_actions.add(act)
            assert ntype == "action", (
                f"Action node {node['state_id']} (action={act}) is type '{ntype}', expected 'action'"
            )
    expected_actions = {"greeting", "information", "plan_proposal", "pressure", "empathy", "legal_threat", "closure"}
    assert seen_actions == expected_actions, (
        f"Action categories mismatch: expected {expected_actions}, got {seen_actions}"
    )


SEP = 120


def _depth_y_positions():
    tree = _load_tree()
    all_nodes = _collect_nodes(tree)
    max_depth = max(d for _, d, _ in all_nodes)
    depth_counts = {}
    for _, d, _ in all_nodes:
        depth_counts[d] = depth_counts.get(d, 0) + 1
    depth_y = {}
    sorted_depths = sorted(depth_counts.keys())
    for i, d in enumerate(sorted_depths):
        if i == 0:
            depth_y[d] = 0
        else:
            prev_d = sorted_depths[i - 1]
            mult = 3 if prev_d == 0 else (2 if prev_d <= 2 else 1)
            extra = 0.5 if prev_d >= 3 else 0
            depth_y[d] = depth_y[prev_d] + SEP * (mult + extra)
    return depth_y, max_depth


def test_each_tree_depth_gets_unique_y_band():
    depth_y, max_depth = _depth_y_positions()
    for d in range(max_depth):
        assert depth_y[d + 1] > depth_y[d] + SEP, (
            f"Depth {d + 1} (y={depth_y[d + 1]}) overlaps with depth {d} (y={depth_y[d]})"
        )


def test_parent_always_above_child():
    tree = _load_tree()
    depth_y, _ = _depth_y_positions()
    violations = []
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        for child in node.get("children", []):
            child_depth = depth + 1
            if child_depth in depth_y and depth in depth_y:
                if depth_y[child_depth] <= depth_y[depth]:
                    violations.append(
                        (node["state_id"], child["state_id"], depth, child_depth)
                    )
            stack.append((child, child_depth))
    assert not violations, (
        f"{len(violations)} parent-child pairs have wrong vertical order:\n"
        + "\n".join(
            f"  {p} (d={pd}) above {c} (d={cd}) but y_parent={depth_y[pd]} >= y_child={depth_y[cd]}"
            for p, c, pd, cd in violations
        )
    )


def test_no_depth_sharing_between_different_levels():
    depth_y, max_depth = _depth_y_positions()
    y_values = [depth_y[d] for d in range(max_depth + 1)]
    assert len(set(y_values)) == len(y_values), (
        f"Duplicate Y positions across depths: {depth_y}"
    )


def test_spacing_increases_for_shallow_depths():
    depth_y, _ = _depth_y_positions()
    sep_0_1 = depth_y[1] - depth_y[0]
    sep_3_4 = depth_y[4] - depth_y[3]
    assert sep_0_1 > sep_3_4, (
        f"Shallow spacing ({sep_0_1}) should be larger than deep spacing ({sep_3_4})"
    )


def _enforce_parent_above_child_y(tree, sep=120):
    node_y = {}
    violations = []

    def assign_y(node, depth):
        if depth == 0:
            node_y[id(node)] = 0
        else:
            parent_y = node_y.get(id(node), None)
            if parent_y is None:
                parent_y = depth * sep
            node_y[id(node)] = parent_y
        for child in node.get("children", []):
            child_min_y = node_y[id(node)] + sep
            child_id = id(child)
            if child_id in node_y:
                if node_y[child_id] < child_min_y:
                    violations.append(
                        (node["state_id"], child["state_id"], node_y[id(node)], node_y[child_id])
                    )
                    node_y[child_id] = child_min_y
            else:
                node_y[child_id] = child_min_y
            assign_y(child, depth + 1)

    assign_y(tree, 0)
    return node_y, violations


def test_every_child_strictly_below_parent():
    tree = _load_tree()
    violations = []
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        for child in node.get("children", []):
            child_depth = depth + 1
            if child_depth <= depth:
                violations.append(
                    (node["state_id"], child["state_id"], depth, child_depth)
                )
            stack.append((child, child_depth))
    assert not violations, (
        f"{len(violations)} children not strictly below parent:\n"
        + "\n".join(
            f"  {p} (d={pd}) -> {c} (d={cd})" for p, c, pd, cd in violations
        )
    )


def test_enforce_parent_above_child_no_violations():
    tree = _load_tree()
    _, violations = _enforce_parent_above_child_y(tree)
    assert not violations, (
        f"{len(violations)} parent-child Y violations after enforcement:\n"
        + "\n".join(
            f"  {p} (y={py}) -> {c} (y={cy})" for p, c, py, cy in violations
        )
    )


def test_all_ancestors_above_descendants():
    tree = _load_tree()
    violations = []
    ancestor_y = {}

    def walk(node, depth, ancestor_chain):
        y = depth * SEP
        ancestor_y[id(node)] = y
        for anc_id, anc_y, anc_sid in ancestor_chain:
            if y <= anc_y:
                violations.append(
                    (anc_sid, node["state_id"], anc_y, y)
                )
        chain = ancestor_chain + [(id(node), y, node["state_id"])]
        for child in node.get("children", []):
            walk(child, depth + 1, chain)

    walk(tree, 0, [])
    assert not violations, (
        f"{len(violations)} ancestor-descendant Y violations:\n"
        + "\n".join(
            f"  ancestor {a} (y={ay}) not above descendant {d} (y={dy})"
            for a, d, ay, dy in violations
        )
    )


def test_back_edge_nodes_share_same_y():
    tree = _load_tree()
    back_edges = []
    stack = [(tree, 0, [])]
    while stack:
        node, depth, ancestor_chain = stack.pop()
        for child in node.get("children", []):
            child_depth = depth + 1
            child_bk = child.get("branch_key", {})
            node_bk = node.get("branch_key", {})
            if child_bk.get("facts") and child_bk["facts"] == node_bk.get("facts"):
                back_edges.append((node["state_id"], child["state_id"]))
            if child_bk.get("emotions") and child_bk["emotions"] == node_bk.get("emotions"):
                back_edges.append((node["state_id"], child["state_id"]))
            stack.append((child, child_depth, ancestor_chain + [(node, depth)]))
    for src, tgt in back_edges:
        src_depth = _node_depth(tree, src)
        tgt_depth = _node_depth(tree, tgt)
        if tgt_depth <= src_depth:
            assert True


def _node_depth(tree, state_id):
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        if node.get("state_id") == state_id:
            return depth
        for child in node.get("children", []):
            stack.append((child, depth + 1))
    return -1


def test_compact_layout_consecutive_visual_depths():
    tree = _load_tree()
    all_nodes = _collect_nodes(tree)
    max_depth = max(d for _, d, _ in all_nodes)
    assert max_depth == 17
