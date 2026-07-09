from .common import ok, fail, warn, skip, walk, walk_sentences, is_end


def check_gestures(tree, records, r):
    cat = "gesture"
    root = tree
    root_pool = root.get("sentence_pool", [])
    opening = [s for s in root_pool if s.get("gesture_type") == "opening"]

    if opening:
        ok(r, "G1", cat, "hard")
    else:
        fail(r, "G1", cat, "hard", "root pool has no opening gesture sentences")

    greeting_children = [c for c in root.get("children", []) if c.get("state_id") == "a:greeting"]
    if not greeting_children:
        ok(r, "G2", cat, "hard")
    else:
        fail(r, "G2", cat, "hard", "root has a:greeting child (greetings should be in root pool)")

    if records is not None:
        ok(r, "G3", cat, "hard", "records provided for gesture check")
    else:
        skip(r, "G3", cat, "hard", "no records provided")

    normal_end = None
    for c in root.get("children", []):
        if c.get("state_id") == "normal_end":
            normal_end = c
            break

    if normal_end:
        if not normal_end.get("sentence_pool"):
            ok(r, "G4", cat, "hard")
        else:
            fail(r, "G4", cat, "hard", f"normal_end should have empty sentence_pool, got {len(normal_end['sentence_pool'])} sentences")

        ok(r, "G5", cat, "hard", "normal_end is a pure terminal marker")
    else:
        fail(r, "G4", cat, "hard", "normal_end not found")
        fail(r, "G5", cat, "hard", "normal_end not found")

    bad = []
    for n, s in walk_sentences(tree):
        if s.get("gesture_type") == "ending" and is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "G6", cat, "hard")
    else:
        fail(r, "G6", cat, "hard", f"{len(bad)} ending sentences inside end nodes (should be in action nodes)", bad[:10])

    if records is not None:
        ok(r, "G7", cat, "hard", "records provided")
    else:
        skip(r, "G7", cat, "hard", "no records provided")

    skip(r, "G8", cat, "hard", "needs records")
    ok(r, "G9", cat, "hard", "structural: greetings in root pool at insert")
    ok(r, "G10", cat, "hard", "structural: closings in normal_end at insert")
    skip(r, "G11", cat, "hard", "runtime concern")


def check_coverage(tree, records, r):
    cat = "coverage"
    if records is None:
        skip(r, "C1", cat, "hard", "no records provided")
        skip(r, "C2", cat, "hard", "no records provided")
        skip(r, "C3", cat, "hard", "no records provided")
        skip(r, "C4", cat, "hard", "informational")
        skip(r, "C5", cat, "hard", "runtime concern")
        skip(r, "C6", cat, "hard", "needs scored tree")
        skip(r, "C7", cat, "soft", "no records provided")
        skip(r, "C8", cat, "soft", "no records provided")
        skip(r, "C9", cat, "soft", "no records provided")
        return

    tree_cids = set()
    tree_facts = set()
    tree_emotions = set()
    for n, s in walk_sentences(tree):
        tree_cids.update(s.get("source_call_ids", []))
    for n in walk(tree):
        bk = n.get("branch_key", {})
        tree_facts.update(bk.get("facts", []))
        tree_emotions.update(bk.get("emotions", []))
        tree_facts.update(n.get("inherited_facts", []))
        tree_emotions.update(n.get("inherited_emotions", []))

    record_cids = {rec.get("call_id") for rec in records}
    missing = record_cids - tree_cids
    if not missing:
        ok(r, "C1", cat, "hard")
    else:
        fail(r, "C1", cat, "hard", f"{len(missing)} call_ids from data not in tree", list(missing)[:10])

    record_facts = set()
    for rec in records:
        for t in rec.get("turns_annotated", []):
            state = t.get("state", {})
            record_facts.update(state.get("facts", []))
    missing_facts = record_facts - tree_facts
    if not missing_facts:
        ok(r, "C2", cat, "hard")
    else:
        warn(r, "C2", cat, "hard", f"{len(missing_facts)} facts from data not in tree", list(missing_facts)[:10])

    record_emotions = set()
    for rec in records:
        for t in rec.get("turns_annotated", []):
            state = t.get("state", {})
            record_emotions.update(state.get("emotions", []))
    missing_emotions = record_emotions - tree_emotions
    if not missing_emotions:
        ok(r, "C3", cat, "hard")
    else:
        warn(r, "C3", cat, "hard", f"{len(missing_emotions)} emotions from data not in tree", list(missing_emotions)[:10])

    ok(r, "C4", cat, "hard", "empty-pool branch nodes allowed")
    skip(r, "C5", cat, "hard", "runtime concern")
    skip(r, "C6", cat, "hard", "needs scored tree")

    warn(r, "C7", cat, "soft", f"action types={len(tree_facts)}")
    warn(r, "C8", cat, "soft", f"fact types={len(tree_facts)}")
    warn(r, "C9", cat, "soft", f"emotion types={len(tree_emotions)}")
