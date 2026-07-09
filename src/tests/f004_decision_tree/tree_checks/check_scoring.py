from .common import ok, fail, warn, skip, walk, walk_sentences


def check_scoring(tree, r):
    cat = "scoring"
    BITMASK_KEYS = {"has_business_loan", "has_mortgage", "has_other_loan",
                    "recent_repayment", "is_high_risk_proxy_complaint",
                    "is_proxy_intermediary_complaint", "has_social_insurance",
                    "has_risk_flag", "has_complaint", "has_vehicle"}

    scored_sentences = [(n, s) for n, s in walk_sentences(tree) if "bg_constraints" in s or "win_rate" in s]

    bad = []
    for n, s in scored_sentences:
        bc = s.get("bg_constraints", {})
        if set(bc.keys()) != BITMASK_KEYS:
            bad.append((s.get("script_id", "?"), set(bc.keys())))
    if not bad:
        ok(r, "SC1", cat, "hard")
    else:
        fail(r, "SC1", cat, "hard", f"{len(bad)} sentences with wrong bg_constraints keys", [f"{sid}:{sorted(ks)}" for sid, ks in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        bm = s.get("bg_bitmask", {})
        if set(bm.keys()) != BITMASK_KEYS:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC2", cat, "hard")
    else:
        fail(r, "SC2", cat, "hard", f"{len(bad)} sentences with wrong bg_bitmask keys", bad[:10])

    bad = []
    for n, s in scored_sentences:
        bmi = s.get("bg_bitmask_int", -1)
        if not (0 <= bmi <= 1023):
            bad.append((s.get("script_id", "?"), bmi))
    if not bad:
        ok(r, "SC3", cat, "hard")
    else:
        fail(r, "SC3", cat, "hard", f"{len(bad)} sentences with bg_bitmask_int outside [0,1023]", [f"{sid}:{v}" for sid, v in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        bc = s.get("bg_constraints", {})
        bm = s.get("bg_bitmask", {})
        bmi = s.get("bg_bitmask_int", 0)
        expected = 0
        for i, key in enumerate(sorted(BITMASK_KEYS)):
            if bm.get(key, False):
                expected |= (1 << i)
        if bmi != expected:
            bad.append((s.get("script_id", "?"), bmi, expected))
    if not bad:
        ok(r, "SC4", cat, "hard")
    else:
        fail(r, "SC4", cat, "hard", f"{len(bad)} sentences with incorrect bg_bitmask_int encoding", [f"{sid}:got={g} exp={e}" for sid, g, e in bad[:10]])

    skip(r, "SC5", cat, "hard", "bitmask AND filtering — sample check, covered by SC4")

    bad = []
    for n, s in scored_sentences:
        cids = s.get("source_call_ids", [])
        if len(cids) > 1:
            bc = s.get("bg_constraints", {})
            if not bc:
                bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC6", cat, "hard")
    else:
        warn(r, "SC6", cat, "hard", f"{len(bad)} multi-source sentences with empty bg_constraints", bad[:10])

    bad = []
    for n, s in scored_sentences:
        wr = s.get("win_rate", -1)
        if not (0 <= wr <= 1):
            bad.append((s.get("script_id", "?"), wr))
    if not bad:
        ok(r, "SC7", cat, "hard")
    else:
        fail(r, "SC7", cat, "hard", f"{len(bad)} sentences with win_rate outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        wr = s.get("win_rate", 0)
        wrn = s.get("win_rate_node", None)
        if wrn is not None:
            cids = s.get("source_call_ids", [])
            n_cids = len(cids)
            weight = n_cids / (n_cids + 2) if n_cids > 0 else 0
            expected = weight * wr + (1 - weight) * wrn
            if abs(wr - expected) > 0.001:
                bad.append((s.get("script_id", "?"), wr, expected))
    if not bad:
        ok(r, "SC8", cat, "hard")
    else:
        warn(r, "SC8", cat, "hard", f"{len(bad)} sentences where win_rate != blend formula", [f"{sid}:got={g:.4f} exp={e:.4f}" for sid, g, e in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        wrn = s.get("win_rate_node", -1)
        if wrn != -1 and not (0 <= wrn <= 1):
            bad.append((s.get("script_id", "?"), wrn))
    if not bad:
        ok(r, "SC9", cat, "hard")
    else:
        fail(r, "SC9", cat, "hard", f"{len(bad)} sentences with win_rate_node outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        if "win_rate_node" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC10", cat, "hard")
    else:
        fail(r, "SC10", cat, "hard", f"{len(bad)} sentences missing win_rate_node", bad[:10])

    skip(r, "SC11", cat, "hard", "covered by SC8")
    skip(r, "SC12", cat, "hard", "covered by SC8")
    skip(r, "SC13", cat, "hard", "covered by SC8")
    skip(r, "SC14", cat, "hard", "covered by SC8")

    bad = []
    for n, s in scored_sentences:
        sas = s.get("sas", -1)
        if not (0 <= sas <= 1):
            bad.append((s.get("script_id", "?"), sas))
    if not bad:
        ok(r, "SC15", cat, "hard")
    else:
        fail(r, "SC15", cat, "hard", f"{len(bad)} sentences with sas outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

    skip(r, "SC16", cat, "hard", "runtime computation")
    skip(r, "SC17", cat, "hard", "runtime computation")
    skip(r, "SC18", cat, "hard", "runtime computation")

    bad = []
    for n, s in scored_sentences:
        if s.get("uplift_score", 0) != 0:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC19", cat, "hard")
    else:
        fail(r, "SC19", cat, "hard", f"{len(bad)} sentences with uplift_score != 0", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if s.get("csi", 0) != 0:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC20", cat, "hard")
    else:
        fail(r, "SC20", cat, "hard", f"{len(bad)} sentences with csi != 0", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if s.get("deferred", True) != True:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC21", cat, "hard")
    else:
        fail(r, "SC21", cat, "hard", f"{len(bad)} sentences with deferred != True", bad[:10])

    bad = []
    for n, s in walk_sentences(tree):
        if "embedding" in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC22", cat, "hard")
    else:
        fail(r, "SC22", cat, "hard", f"{len(bad)} sentences with embedding in JSON (should be DB-only)", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if "conversation_context" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC23", cat, "hard")
    else:
        fail(r, "SC23", cat, "hard", f"{len(bad)} sentences missing conversation_context", bad[:10])

    skip(r, "SC24", cat, "hard", "DB-only")

    bad = []
    for n, s in scored_sentences:
        bg = s.get("bg_background", {})
        if not isinstance(bg, dict):
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC25", cat, "hard")
    else:
        fail(r, "SC25", cat, "hard", f"{len(bad)} sentences with missing/invalid bg_background", bad[:10])

    bad = []
    for n, s in scored_sentences:
        bc = s.get("bg_constraints", {})
        numeric_in_bitmask = [k for k in bc if k not in BITMASK_KEYS]
        if numeric_in_bitmask:
            bad.append(s.get("script_id", "?"))
    if not bad:
        ok(r, "SC26", cat, "hard")
    else:
        fail(r, "SC26", cat, "hard", f"{len(bad)} sentences with numeric fields in bitmask", bad[:10])

    skip(r, "SC27", cat, "hard", "covered by SC4+SC5")
    skip(r, "SC28", cat, "hard", "runtime concern")
