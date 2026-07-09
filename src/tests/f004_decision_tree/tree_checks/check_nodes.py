from .common import ok, fail, skip, walk, is_end, node_identity


def check_nodes(tree, r):
    cat = "node"
    VALID_ROLES = {"opening", "ending", "decision", "action"}
    bad = []

    for n in walk(tree):
        if is_end(n):
            continue
        if "node_id" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N1", cat, "hard")
    else:
        fail(r, "N1", cat, "hard", f"{len(bad)} non-end nodes missing node_id", bad[:10])

    bad = []
    for n in walk(tree):
        if is_end(n):
            continue
        if "inherited_facts" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N2", cat, "hard")
    else:
        fail(r, "N2", cat, "hard", f"{len(bad)} non-end nodes missing inherited_facts", bad[:10])

    bad = []
    for n in walk(tree):
        if is_end(n):
            continue
        if "inherited_emotions" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N3", cat, "hard")
    else:
        fail(r, "N3", cat, "hard", f"{len(bad)} non-end nodes missing inherited_emotions", bad[:10])

    bad = []
    for n in walk(tree):
        role = n.get("role")
        if role is not None and role not in VALID_ROLES:
            bad.append((n.get("state_id", "?"), role))
    if not bad:
        ok(r, "N4", cat, "hard")
    else:
        fail(r, "N4", cat, "hard", f"{len(bad)} nodes with invalid role", [f"{s}:{rl}" for s, rl in bad[:10]])

    skip(r, "N5", cat, "hard", "covered by S2")
    skip(r, "N6", cat, "hard", "covered by S6")

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk or "emotions" in bk:
            for c in n.get("children", []):
                cbk = c.get("branch_key", {})
                if ("facts" in cbk or "emotions" in cbk) and c.get("role") not in (None, "decision"):
                    bad.append(c.get("state_id", "?"))
    if not bad:
        ok(r, "N7", cat, "hard")
    else:
        fail(r, "N7", cat, "hard", f"{len(bad)} fact/emotion children without role=decision", bad[:10])

    bad = []
    for n in walk(tree):
        for c in n.get("children", []):
            cbk = c.get("branch_key", {})
            if "action" in cbk and c.get("role") not in (None, "action"):
                bad.append(c.get("state_id", "?"))
    if not bad:
        ok(r, "N8", cat, "hard")
    else:
        fail(r, "N8", cat, "hard", f"{len(bad)} action children without role=action", bad[:10])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk and "emotions" in bk:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N9", cat, "hard")
    else:
        fail(r, "N9", cat, "hard", f"{len(bad)} nodes with composite branch keys (facts+emotions)", bad[:10])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk and len(bk["facts"]) > 1:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N10", cat, "hard")
    else:
        fail(r, "N10", cat, "hard", f"{len(bad)} nodes with multi-fact branch keys", bad[:10])

    bad = []
    for n in walk(tree):
        if n is tree:
            continue
        bk = n.get("branch_key", {})
        if bk and len(bk) != 1:
            bad.append((n.get("state_id", "?"), list(bk.keys())))
    if not bad:
        ok(r, "N11", cat, "hard")
    else:
        fail(r, "N11", cat, "hard", f"{len(bad)} nodes with branch_key != 1 top-level key", [f"{s}:{k}" for s, k in bad[:10]])

    bad = []
    for n in walk(tree):
        seen_identity = {}
        for c in n.get("children", []):
            ident = node_identity(c)
            if ident in seen_identity:
                bad.append((n.get("state_id", "?"), c.get("state_id", "?")))
            else:
                seen_identity[ident] = c
    if not bad:
        ok(r, "N12", cat, "hard")
    else:
        fail(r, "N12", cat, "hard", f"{len(bad)} duplicate sibling nodes by identity", [f"parent={p} child={c}" for p, c in bad[:10]])

    skip(r, "N13", cat, "hard", "same as N12")

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        own_facts = bk.get("facts", [])
        inh = n.get("inherited_facts", [])
        for f in own_facts:
            if f in inh:
                bad.append((n.get("state_id", "?"), f))
    if not bad:
        ok(r, "N14", cat, "hard")
    else:
        fail(r, "N14", cat, "hard", f"{len(bad)} nodes where own fact in inherited_facts", [f"{s}:{f}" for s, f in bad[:10]])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        own_emotions = bk.get("emotions", [])
        inh = n.get("inherited_emotions", [])
        for e in own_emotions:
            if e in inh:
                bad.append((n.get("state_id", "?"), e))
    if not bad:
        ok(r, "N15", cat, "hard")
    else:
        fail(r, "N15", cat, "hard", f"{len(bad)} nodes where own emotion in inherited_emotions", [f"{s}:{e}" for s, e in bad[:10]])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        own_facts = bk.get("facts", [])
        inh = n.get("inherited_facts", [])
        for f in own_facts:
            if f in inh:
                bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N16", cat, "hard")
    else:
        fail(r, "N16", cat, "hard", f"{len(bad)} redundant fact nodes", bad[:10])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        own_emotions = bk.get("emotions", [])
        inh = n.get("inherited_emotions", [])
        for e in own_emotions:
            if e in inh:
                bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N17", cat, "hard")
    else:
        fail(r, "N17", cat, "hard", f"{len(bad)} redundant emotion nodes", bad[:10])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        for key in ("facts", "emotions"):
            if key in bk and bk[key] != sorted(bk[key]):
                bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N18", cat, "hard")
    else:
        fail(r, "N18", cat, "hard", f"{len(bad)} nodes with unsorted keywords in branch_key", bad[:10])

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        sid = n.get("state_id", "")
        if "action" in bk:
            if not sid.startswith("a:"):
                bad.append(sid)
            if n.get("role") not in (None, "action"):
                bad.append(sid)
    if not bad:
        ok(r, "N19", cat, "hard")
    else:
        fail(r, "N19", cat, "hard", f"{len(bad)} action nodes with wrong state_id or role", bad[:10])

    bad = []
    for n in walk(tree):
        if is_end(n):
            bk = n.get("branch_key", {})
            if "end_type" not in bk:
                bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "N20", cat, "hard")
    else:
        fail(r, "N20", cat, "hard", f"{len(bad)} end nodes without end_type in branch_key", bad[:10])

    skip(r, "N21", cat, "hard", "runtime concern")
    skip(r, "N22", cat, "hard", "runtime concern")
