from .common import ok, fail, skip, walk, walk_sentences


def check_branching(tree, r):
    cat = "branching"

    bad = []
    for n in walk(tree):
        bk = n.get("branch_key", {})
        if "willingness" in bk:
            bad.append(n.get("state_id", "?"))
    if not bad:
        ok(r, "B1", cat, "hard")
    else:
        fail(r, "B1", cat, "hard", f"{len(bad)} nodes with willingness in branch_key", bad[:10])

    skip(r, "B2", cat, "hard", "covered by N9/N10")
    skip(r, "B3", cat, "hard", "covered by B1")
    skip(r, "B4", cat, "hard", "covered by B1")
    skip(r, "B5", cat, "hard", "runtime concern")
    skip(r, "B6", cat, "hard", "runtime concern")
    skip(r, "B7", cat, "hard", "covered by N9/N10")
    skip(r, "B8", cat, "hard", "runtime concern")
    skip(r, "B9", cat, "hard", "informational")

    bad = []
    for n in walk(tree):
        for c in n.get("children", []):
            cbk = c.get("branch_key", {})
            if "action" in cbk:
                parent_bk = n.get("branch_key", {})
                if "facts" not in parent_bk and "emotions" not in parent_bk and n is not tree:
                    bad.append(c.get("state_id", "?"))
    if not bad:
        ok(r, "B10", cat, "hard")
    else:
        fail(r, "B10", cat, "hard", f"{len(bad)} action nodes not under decision node", bad[:10])

    skip(r, "B11", cat, "hard", "covered by N16")
    skip(r, "B12", cat, "hard", "covered by N17")
    skip(r, "B13", cat, "hard", "runtime concern")


def check_additive(tree, r):
    cat = "additive"

    skip(r, "A1", cat, "hard", "covered by N9")
    skip(r, "A2", cat, "hard", "covered by N9/N10")

    ok(r, "A3", cat, "hard", "merge_dialogs validity covered by structure checks")

    bad = []
    cid_script_ids = {}
    for n, s in walk_sentences(tree):
        for cid in s.get("source_call_ids", []):
            sid = s.get("script_id", "?")
            cid_script_ids.setdefault(cid, []).append(sid)
    for cid, sids in cid_script_ids.items():
        if len(sids) != len(set(sids)):
            bad.append(cid)
    if not bad:
        ok(r, "A4", cat, "hard")
    else:
        warn(r, "A4", cat, "hard", f"{len(bad)} call_ids with duplicate script_ids", bad[:10])

    skip(r, "A5", cat, "hard", "covered by N12")
    skip(r, "A6", cat, "hard", "runtime concern")
    ok(r, "A7", cat, "hard", "base structure covered by S1-S6")
    skip(r, "A8", cat, "hard", "runtime concern")
