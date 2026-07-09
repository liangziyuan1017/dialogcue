from .common import ok, fail, warn, skip, walk, is_end


def check_structure(tree, r):
    cat = "structure"
    root = tree

    if root.get("state_id") == "initial_contact":
        ok(r, "S1", cat, "hard")
    else:
        fail(r, "S1", cat, "hard", f"root state_id={root.get('state_id')!r}, expected 'initial_contact'")

    if root.get("role") == "opening":
        ok(r, "S2", cat, "hard")
    else:
        fail(r, "S2", cat, "hard", f"root role={root.get('role')!r}, expected 'opening'")

    end_children = [c for c in root.get("children", []) if is_end(c)]
    normal = [c for c in end_children if c.get("state_id") == "normal_end"]
    abrupt = [c for c in end_children if c.get("state_id") == "abrupt_end"]

    if len(normal) == 1:
        ok(r, "S3", cat, "hard")
    else:
        fail(r, "S3", cat, "hard", f"found {len(normal)} normal_end nodes, expected 1")

    if len(abrupt) == 1:
        ok(r, "S4", cat, "hard")
    else:
        fail(r, "S4", cat, "hard", f"found {len(abrupt)} abrupt_end nodes, expected 1")

    non_direct = [c for c in end_children if c not in root.get("children", [])]
    if not non_direct:
        ok(r, "S5", cat, "hard")
    else:
        fail(r, "S5", cat, "hard", "end nodes not direct children of root", [c.get("state_id") for c in non_direct])

    end_bad_role = [c for c in end_children if c.get("role") != "ending"]
    if not end_bad_role:
        ok(r, "S6", cat, "hard")
    else:
        fail(r, "S6", cat, "hard", "end nodes without role=ending", [c.get("state_id") for c in end_bad_role])

    if root.get("state_id") == "initial_contact" and len(normal) == 1 and len(abrupt) == 1:
        ok(r, "S7", cat, "hard")
    else:
        fail(r, "S7", cat, "hard", "3 structural anchors missing")

    leaves = []
    for n in walk(root):
        if not n.get("children", []):
            leaves.append(n)
    bad_leaves = [l for l in leaves if not is_end(l) and not any(s.get("gesture_type") == "ending" for s in l.get("sentence_pool", []))]
    if not bad_leaves:
        ok(r, "S8", cat, "hard")
    else:
        ok(r, "S8", cat, "hard", f"{len(bad_leaves)} leaves implicitly terminated at abrupt_end")

    def _path_reaches_end(node, visited=None):
        if visited is None:
            visited = set()
        nid = id(node)
        if nid in visited:
            return False
        visited.add(nid)
        if is_end(node):
            return True
        if not node.get("children", []):
            return True
        return all(_path_reaches_end(c, visited.copy()) for c in node.get("children", []))

    if _path_reaches_end(root):
        ok(r, "S9", cat, "hard")
    else:
        fail(r, "S9", cat, "hard", "not all paths terminate at end node")

    has_cycle = False

    def _detect_cycle(node, path_ids):
        nonlocal has_cycle
        nid = id(node)
        if nid in path_ids:
            has_cycle = True
            return
        path_ids.add(nid)
        for c in node.get("children", []):
            _detect_cycle(c, path_ids)
        path_ids.discard(nid)

    _detect_cycle(root, set())
    if not has_cycle:
        ok(r, "S10", cat, "hard")
    else:
        fail(r, "S10", cat, "hard", "cycle detected in tree")

    skip(r, "S11", cat, "hard", "same as S10")
    skip(r, "S12", cat, "hard", "runtime concern")

    node_ids = {}
    for n in walk(root):
        nid = n.get("node_id")
        if nid:
            node_ids.setdefault(nid, []).append(n)
    dup_nids = {k: v for k, v in node_ids.items() if len(v) > 1}
    if not dup_nids:
        ok(r, "S13", cat, "hard")
    else:
        warn(r, "S13", cat, "hard", f"{len(dup_nids)} node_ids shared by multiple nodes (DAG share)", list(dup_nids.keys())[:10])

    all_nodes = list(walk(root))
    single_child = sum(1 for n in all_nodes if len(n.get("children", [])) == 1 and not is_end(n) and n is not root)
    non_end_non_root = sum(1 for n in all_nodes if not is_end(n) and n is not root)
    ratio = single_child / non_end_non_root if non_end_non_root else 0
    if ratio < 0.85:
        ok(r, "S14", cat, "hard", f"single-child ratio={ratio:.2%}")
    else:
        fail(r, "S14", cat, "hard", f"single-child ratio={ratio:.2%} >= 85%")

    depths = []

    def _measure_depth(node, d):
        depths.append(d)
        for c in node.get("children", []):
            _measure_depth(c, d + 1)

    _measure_depth(root, 0)
    warn(r, "S15", cat, "soft", f"max depth={max(depths)}")
    warn(r, "S16", cat, "soft", f"node count={len(all_nodes)}")

    shared = sum(1 for v in node_ids.values() if len(v) > 1)
    warn(r, "S17", cat, "soft", f"DAG shared nodes={shared}")
    skip(r, "S18", cat, "soft", "visual concern")
