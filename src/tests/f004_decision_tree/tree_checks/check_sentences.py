from .common import ok, fail, warn, skip, walk, walk_sentences, is_end


def check_sentences(tree, r):
    cat = "sentence"
    REQUIRED = ["script_text", "script_id", "source_call_ids", "customer_willingness"]

    for i, field in enumerate(REQUIRED, 1):
        bad = []
        for n, s in walk_sentences(tree):
            if field not in s:
                bad.append(s.get("script_id", "?"))
        if not bad:
            ok(r, f"SE{i}", cat, "hard")
        else:
            fail(r, f"SE{i}", cat, "hard", f"{len(bad)} sentences missing {field}", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if s.get("collector_action") and "fact_context" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE5", cat, "hard")
    else:
        fail(r, "SE5", cat, "hard", f"{len(bad)} sentences with collector_action but no fact_context", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if "fact_context" not in s and not is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE6", cat, "hard")
    else:
        fail(r, "SE6", cat, "hard", f"{len(bad)} sentences missing fact_context", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if s.get("collector_action"):
            parent_bk = n.get("branch_key", {})
            if "action" not in parent_bk and not is_end(n) and n is not tree:
                bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE7", cat, "hard")
    else:
        fail(r, "SE7", cat, "hard", f"{len(bad)} action sentences not under action node", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if not s.get("collector_action") and "action" in n.get("branch_key", {}):
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE8", cat, "hard")
    else:
        fail(r, "SE8", cat, "hard", f"{len(bad)} non-action sentences in action node pool", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if s.get("customer_willingness") is None and s.get("collector_action") and "gesture_type" not in s and not is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE9", cat, "hard")
    else:
        warn(r, "SE9", cat, "hard", f"{len(bad)} state=None turns with collector_action", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if s.get("collector_action") == "other":
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE10", cat, "hard")
    else:
        fail(r, "SE10", cat, "hard", f"{len(bad)} sentences with synthetic 'other' action", bad[:10])

    skip(r, "SE11", cat, "hard", "covered by SE9")

    bad = []
    for n in walk(tree):
        if not n.get("children", []) and not is_end(n) and not n.get("sentence_pool", []):
            if n is not tree:
                bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "SE12", cat, "hard")
    else:
        warn(r, "SE12", cat, "hard", f"{len(bad)} leaf nodes with empty sentence_pool (implicitly reach abrupt_end)", bad[:10])

    bad = []
    for n in walk(tree):
        texts = [s.get("script_text", "") for s in n.get("sentence_pool", [])]
        if len(texts) != len(set(texts)):
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "SE13", cat, "hard")
    else:
        warn(r, "SE13", cat, "hard", f"{len(bad)} nodes with duplicate script_text in pool", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if len(s.get("script_text", "")) > 150:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SE14", cat, "hard")
    else:
        warn(r, "SE14", cat, "hard", f"{len(bad)} sentences > 150 chars", bad[:10])

    skip(r, "SE15", cat, "hard", "runtime concern")
    skip(r, "SE16", cat, "hard", "runtime concern")


def check_termination(tree, r):
    cat = "termination"

    end_nodes = []
    for n in walk(tree):
        if is_end(n):
            end_nodes.append(n)
    if len(end_nodes) == 2:
        ok(r, "T1", cat, "hard")
    else:
        fail(r, "T1", cat, "hard", f"found {len(end_nodes)} end nodes, expected exactly 2 (1 normal_end + 1 abrupt_end)", [n.get("state_id", "?") for n in end_nodes[:10]])

    bad = []
    for n in end_nodes:
        if n.get("sentence_pool", []):
            bad.append((n.get("state_id", "?"), len(n.get("sentence_pool", []))))
    if not bad:
        ok(r, "T2", cat, "hard")
    else:
        fail(r, "T2", cat, "hard", f"{len(bad)} end nodes with non-empty sentence_pool", [f"{sid}:{cnt}" for sid, cnt in bad[:10]])

    bad = []
    root_children = tree.get("children", [])
    for n in end_nodes:
        if any(n is c for c in root_children):
            continue
        bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "T3", cat, "hard")
    else:
        fail(r, "T3", cat, "hard", f"{len(bad)} end nodes not direct children of root", bad[:10])

    def _subtree_has_sentences(node, _visited=None):
        if _visited is None:
            _visited = set()
        nid = id(node)
        if nid in _visited:
            return False
        _visited.add(nid)
        if node.get("sentence_pool"):
            return True
        return any(_subtree_has_sentences(c, _visited) for c in node.get("children", []))

    bad = []
    for n in walk(tree):
        if is_end(n) or n is tree:
            continue
        role = n.get("role", "")
        if role == "action":
            continue
        bk = n.get("branch_key", {})
        if not bk:
            continue
        if not _subtree_has_sentences(n):
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "T4", cat, "hard")
    else:
        fail(r, "T4", cat, "hard", f"{len(bad)} empty fact/emotion subtrees (no sentences in entire subtree)", bad[:10])

    bad = []
    for n in walk(tree):
        if is_end(n) or n is tree:
            continue
        for c in n.get("children", []):
            if is_end(c):
                bad.append((n.get("state_id", "?"), c.get("state_id", "?")))
    if not bad:
        ok(r, "T5", cat, "hard")
    else:
        fail(r, "T5", cat, "hard", f"{len(bad)} non-root nodes with end node children", [f"{p}->{c}" for p, c in bad[:10]])
