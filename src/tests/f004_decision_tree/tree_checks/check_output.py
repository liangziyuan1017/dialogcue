from .common import ok, fail, warn, skip, walk, walk_sentences, is_end, node_identity, trace_call_id


def check_output(tree, scored_tree, r):
    cat = "output"

    if tree is not None:
        ok(r, "O1", cat, "hard", "decision_tree.json loaded")
    else:
        fail(r, "O1", cat, "hard", "decision_tree.json not loaded")

    if scored_tree is not None:
        ok(r, "O2", cat, "hard", "decision_tree_scored.json loaded")
    else:
        skip(r, "O2", cat, "hard", "scored tree not provided")

    if tree and scored_tree:
        tree_sids = set()
        scored_sids = set()
        for n in walk(tree):
            tree_sids.add(n.get("state_id", ""))
        for n in walk(scored_tree):
            scored_sids.add(n.get("state_id", ""))
        missing = tree_sids - scored_sids
        extra = scored_sids - tree_sids
        if not missing and not extra:
            ok(r, "O3", cat, "hard")
        else:
            fail(r, "O3", cat, "hard", f"node mismatch: {len(missing)} missing, {len(extra)} extra",
                 list(missing)[:5] + list(extra)[:5])

        scored_fields = {"bg_constraints", "bg_bitmask", "bg_bitmask_int", "win_rate", "sas",
                         "uplift_score", "csi", "deferred", "conversation_context", "bg_background"}
        bad = []
        for n, s in walk_sentences(scored_tree):
            missing_f = scored_fields - set(s.keys())
            if missing_f:
                bad.append((s.get("script_id", "?"), missing_f))
        if not bad:
            ok(r, "O4", cat, "hard")
        else:
            fail(r, "O4", cat, "hard", f"{len(bad)} scored sentences missing fields", [f"{sid}:{sorted(mf)}" for sid, mf in bad[:10]])
    else:
        skip(r, "O3", cat, "hard", "need both trees")
        skip(r, "O4", cat, "hard", "need scored tree")

    skip(r, "O5", cat, "hard", "DB-only")
    skip(r, "O6", cat, "hard", "DB-only")
    skip(r, "O7", cat, "hard", "DB-only")
    skip(r, "O8", cat, "hard", "DB-only")


def check_per_dialog(tree, records, r):
    cat = "per_dialog"

    if records is None:
        skip(r, "D1", cat, "hard", "no records provided")
        skip(r, "D2", cat, "hard", "no records provided")
        skip(r, "D3", cat, "hard", "no records provided")
    else:
        bad_d1 = []
        bad_d2 = []
        bad_d3 = []
        for rec in records:
            cid = rec.get("call_id")
            path = trace_call_id(tree, cid)
            facts = []
            emotions = []
            for node in path:
                bk = node.get("branch_key", {})
                facts.extend(bk.get("facts", []))
                emotions.extend(bk.get("emotions", []))
            if len(facts) != len(set(facts)):
                bad_d1.append(cid)
            if len(emotions) != len(set(emotions)):
                bad_d2.append(cid)
            if path:
                last = path[-1]
                if not is_end(last):
                    terminates = any(is_end(c) for c in last.get("children", []))
                    if not terminates:
                        bad_d3.append(cid)

        if not bad_d1:
            ok(r, "D1", cat, "hard")
        else:
            warn(r, "D1", cat, "hard", f"{len(bad_d1)} dialogs with duplicate facts in path", bad_d1[:10])

        if not bad_d2:
            ok(r, "D2", cat, "hard")
        else:
            warn(r, "D2", cat, "hard", f"{len(bad_d2)} dialogs with duplicate emotions in path", bad_d2[:10])

        if not bad_d3:
            ok(r, "D3", cat, "hard")
        else:
            warn(r, "D3", cat, "hard", f"{len(bad_d3)} dialogs not reaching end node", bad_d3[:10])

    all_sids = []
    for n, s in walk_sentences(tree):
        all_sids.append(s.get("script_id", "?"))
    dup_sids = len(all_sids) - len(set(all_sids))
    if dup_sids == 0:
        ok(r, "D4", cat, "hard")
    else:
        warn(r, "D4", cat, "hard", f"{dup_sids} duplicate script_ids")

    identity_map = {}
    bad_d5 = []
    for n in walk(tree):
        ident = node_identity(n)
        if ident in identity_map and identity_map[ident] is not n:
            bad_d5.append(n.get("state_id", "?"))
        else:
            identity_map[ident] = n
    if not bad_d5:
        ok(r, "D5", cat, "hard")
    else:
        warn(r, "D5", cat, "hard", f"{len(bad_d5)} duplicate nodes by identity", bad_d5[:10])
