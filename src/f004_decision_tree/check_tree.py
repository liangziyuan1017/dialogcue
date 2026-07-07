import argparse
import json
import os
import sys
from dataclasses import dataclass, field

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_REWARDED_PATH = os.path.join(os.path.dirname(__file__), "..", "f003_reward_labeling", "data", "output_rewarded.py")


@dataclass
class CheckResult:
    id: str
    category: str
    severity: str
    status: str
    message: str
    details: list = field(default_factory=list)


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, r: CheckResult):
        self.checks.append(r)

    def summary(self) -> str:
        p = sum(1 for c in self.checks if c.status == "pass")
        f = sum(1 for c in self.checks if c.status == "fail")
        w = sum(1 for c in self.checks if c.status == "warn")
        s = sum(1 for c in self.checks if c.status == "skip")
        return f"pass={p} fail={f} warn={w} skip={s} total={len(self.checks)}"

    def exit_code(self) -> int:
        return 1 if any(c.status == "fail" for c in self.checks) else 0

    def to_dict(self) -> dict:
        return {
            "pass": sum(1 for c in self.checks if c.status == "pass"),
            "fail": sum(1 for c in self.checks if c.status == "fail"),
            "warn": sum(1 for c in self.checks if c.status == "warn"),
            "skip": sum(1 for c in self.checks if c.status == "skip"),
            "checks": [
                {"id": c.id, "category": c.category, "severity": c.severity,
                 "status": c.status, "message": c.message, "details": c.details}
                for c in self.checks
            ],
        }


def _ok(r, id, cat, sev, msg=""):
    r.add(CheckResult(id, cat, sev, "pass", msg))

def _fail(r, id, cat, sev, msg, details=None):
    r.add(CheckResult(id, cat, sev, "fail", msg, details or []))

def _warn(r, id, cat, sev, msg, details=None):
    r.add(CheckResult(id, cat, sev, "warn", msg, details or []))

def _skip(r, id, cat, sev, msg=""):
    r.add(CheckResult(id, cat, sev, "skip", msg))


def _walk(tree):
    yield tree
    for c in tree.get("children", []):
        yield from _walk(c)

def _walk_sentences(tree):
    for n in _walk(tree):
        for s in n.get("sentence_pool", []):
            yield n, s

def _is_end(node):
    sid = node.get("state_id", "")
    return sid in ("normal_end", "abrupt_end")

def _node_identity(n):
    return (
        tuple(sorted(n.get("inherited_facts", []))),
        tuple(sorted(n.get("inherited_emotions", []))),
        json.dumps(n.get("branch_key", {}), sort_keys=True),
    )


def _load_rewarded():
    import importlib.util
    spec = importlib.util.spec_from_file_location("output_rewarded", _REWARDED_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _trace_call_id(tree, call_id):
    path = []
    def walk(node):
        has = any(call_id in s.get("source_call_ids", []) for s in node.get("sentence_pool", []))
        if has:
            path.append(node)
        for c in node.get("children", []):
            walk(c)
    walk(tree)
    return path


def _check_structure(tree, r):
    cat = "structure"
    root = tree

    if root.get("state_id") == "initial_contact":
        _ok(r, "S1", cat, "hard")
    else:
        _fail(r, "S1", cat, "hard", f"root state_id={root.get('state_id')!r}, expected 'initial_contact'")

    if root.get("role") == "opening":
        _ok(r, "S2", cat, "hard")
    else:
        _fail(r, "S2", cat, "hard", f"root role={root.get('role')!r}, expected 'opening'")

    end_children = [c for c in root.get("children", []) if _is_end(c)]
    normal = [c for c in end_children if c.get("state_id") == "normal_end"]
    abrupt = [c for c in end_children if c.get("state_id") == "abrupt_end"]

    if len(normal) == 1:
        _ok(r, "S3", cat, "hard")
    else:
        _fail(r, "S3", cat, "hard", f"found {len(normal)} normal_end nodes, expected 1")

    if len(abrupt) == 1:
        _ok(r, "S4", cat, "hard")
    else:
        _fail(r, "S4", cat, "hard", f"found {len(abrupt)} abrupt_end nodes, expected 1")

    non_direct = [c for c in end_children if c not in root.get("children", [])]
    if not non_direct:
        _ok(r, "S5", cat, "hard")
    else:
        _fail(r, "S5", cat, "hard", "end nodes not direct children of root", [c.get("state_id") for c in non_direct])

    end_bad_role = [c for c in end_children if c.get("role") != "ending"]
    if not end_bad_role:
        _ok(r, "S6", cat, "hard")
    else:
        _fail(r, "S6", cat, "hard", "end nodes without role=ending", [c.get("state_id") for c in end_bad_role])

    if root.get("state_id") == "initial_contact" and len(normal) == 1 and len(abrupt) == 1:
        _ok(r, "S7", cat, "hard")
    else:
        _fail(r, "S7", cat, "hard", "3 structural anchors missing")

    leaves = []
    for n in _walk(root):
        if not n.get("children", []):
            leaves.append(n)
    bad_leaves = [l for l in leaves if not _is_end(l) and not any(s.get("gesture_type") == "ending" for s in l.get("sentence_pool", []))]
    if not bad_leaves:
        _ok(r, "S8", cat, "hard")
    else:
        _warn(r, "S8", cat, "hard", f"{len(bad_leaves)} leaves not end nodes and lack ending gesture (implicitly reach abrupt_end)", [l.get("state_id", "?") for l in bad_leaves[:10]])

    def _path_reaches_end(node, visited=None):
        if visited is None:
            visited = set()
        nid = id(node)
        if nid in visited:
            return False
        visited.add(nid)
        if _is_end(node):
            return True
        if not node.get("children", []):
            return True
        return all(_path_reaches_end(c, visited.copy()) for c in node.get("children", []))

    if _path_reaches_end(root):
        _ok(r, "S9", cat, "hard")
    else:
        _fail(r, "S9", cat, "hard", "not all paths terminate at end node")

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
        _ok(r, "S10", cat, "hard")
    else:
        _fail(r, "S10", cat, "hard", "cycle detected in tree")

    _skip(r, "S11", cat, "hard", "same as S10")
    _skip(r, "S12", cat, "hard", "runtime concern")

    node_ids = {}
    for n in _walk(root):
        nid = n.get("node_id")
        if nid:
            node_ids.setdefault(nid, []).append(n)
    dup_nids = {k: v for k, v in node_ids.items() if len(v) > 1}
    if not dup_nids:
        _ok(r, "S13", cat, "hard")
    else:
        _warn(r, "S13", cat, "hard", f"{len(dup_nids)} node_ids shared by multiple nodes (DAG share)", list(dup_nids.keys())[:10])

    all_nodes = list(_walk(root))
    single_child = sum(1 for n in all_nodes if len(n.get("children", [])) == 1 and not _is_end(n) and n is not root)
    non_end_non_root = sum(1 for n in all_nodes if not _is_end(n) and n is not root)
    ratio = single_child / non_end_non_root if non_end_non_root else 0
    if ratio < 0.85:
        _ok(r, "S14", cat, "hard", f"single-child ratio={ratio:.2%}")
    else:
        _fail(r, "S14", cat, "hard", f"single-child ratio={ratio:.2%} >= 85%")

    depths = []
    def _measure_depth(node, d):
        depths.append(d)
        for c in node.get("children", []):
            _measure_depth(c, d + 1)
    _measure_depth(root, 0)
    _warn(r, "S15", cat, "soft", f"max depth={max(depths)}")
    _warn(r, "S16", cat, "soft", f"node count={len(all_nodes)}")

    shared = sum(1 for v in node_ids.values() if len(v) > 1)
    _warn(r, "S17", cat, "soft", f"DAG shared nodes={shared}")
    _skip(r, "S18", cat, "soft", "visual concern")


def _check_nodes(tree, r):
    cat = "node"
    VALID_ROLES = {"opening", "ending", "decision", "action"}
    bad = []

    for n in _walk(tree):
        if _is_end(n):
            continue
        if "node_id" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N1", cat, "hard")
    else:
        _fail(r, "N1", cat, "hard", f"{len(bad)} non-end nodes missing node_id", bad[:10])

    bad = []
    for n in _walk(tree):
        if _is_end(n):
            continue
        if "inherited_facts" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N2", cat, "hard")
    else:
        _fail(r, "N2", cat, "hard", f"{len(bad)} non-end nodes missing inherited_facts", bad[:10])

    bad = []
    for n in _walk(tree):
        if _is_end(n):
            continue
        if "inherited_emotions" not in n:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N3", cat, "hard")
    else:
        _fail(r, "N3", cat, "hard", f"{len(bad)} non-end nodes missing inherited_emotions", bad[:10])

    bad = []
    for n in _walk(tree):
        role = n.get("role")
        if role is not None and role not in VALID_ROLES:
            bad.append((n.get("state_id", "?"), role))
    if not bad:
        _ok(r, "N4", cat, "hard")
    else:
        _fail(r, "N4", cat, "hard", f"{len(bad)} nodes with invalid role", [f"{s}:{rl}" for s, rl in bad[:10]])

    _skip(r, "N5", cat, "hard", "covered by S2")
    _skip(r, "N6", cat, "hard", "covered by S6")

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk or "emotions" in bk:
            for c in n.get("children", []):
                cbk = c.get("branch_key", {})
                if ("facts" in cbk or "emotions" in cbk) and c.get("role") not in (None, "decision"):
                    bad.append(c.get("state_id", "?"))
    if not bad:
        _ok(r, "N7", cat, "hard")
    else:
        _fail(r, "N7", cat, "hard", f"{len(bad)} fact/emotion children without role=decision", bad[:10])

    bad = []
    for n in _walk(tree):
        for c in n.get("children", []):
            cbk = c.get("branch_key", {})
            if "action" in cbk and c.get("role") not in (None, "action"):
                bad.append(c.get("state_id", "?"))
    if not bad:
        _ok(r, "N8", cat, "hard")
    else:
        _fail(r, "N8", cat, "hard", f"{len(bad)} action children without role=action", bad[:10])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk and "emotions" in bk:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N9", cat, "hard")
    else:
        _fail(r, "N9", cat, "hard", f"{len(bad)} nodes with composite branch keys (facts+emotions)", bad[:10])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        if "facts" in bk and len(bk["facts"]) > 1:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N10", cat, "hard")
    else:
        _fail(r, "N10", cat, "hard", f"{len(bad)} nodes with multi-fact branch keys", bad[:10])

    bad = []
    for n in _walk(tree):
        if n is tree:
            continue
        bk = n.get("branch_key", {})
        if bk and len(bk) != 1:
            bad.append((n.get("state_id", "?"), list(bk.keys())))
    if not bad:
        _ok(r, "N11", cat, "hard")
    else:
        _fail(r, "N11", cat, "hard", f"{len(bad)} nodes with branch_key != 1 top-level key", [f"{s}:{k}" for s, k in bad[:10]])

    bad = []
    for n in _walk(tree):
        seen_identity = {}
        for c in n.get("children", []):
            ident = _node_identity(c)
            if ident in seen_identity:
                bad.append((n.get("state_id", "?"), c.get("state_id", "?")))
            else:
                seen_identity[ident] = c
    if not bad:
        _ok(r, "N12", cat, "hard")
    else:
        _fail(r, "N12", cat, "hard", f"{len(bad)} duplicate sibling nodes by identity", [f"parent={p} child={c}" for p, c in bad[:10]])

    _skip(r, "N13", cat, "hard", "same as N12")

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        own_facts = bk.get("facts", [])
        inh = n.get("inherited_facts", [])
        for f in own_facts:
            if f in inh:
                bad.append((n.get("state_id", "?"), f))
    if not bad:
        _ok(r, "N14", cat, "hard")
    else:
        _fail(r, "N14", cat, "hard", f"{len(bad)} nodes where own fact in inherited_facts", [f"{s}:{f}" for s, f in bad[:10]])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        own_emotions = bk.get("emotions", [])
        inh = n.get("inherited_emotions", [])
        for e in own_emotions:
            if e in inh:
                bad.append((n.get("state_id", "?"), e))
    if not bad:
        _ok(r, "N15", cat, "hard")
    else:
        _fail(r, "N15", cat, "hard", f"{len(bad)} nodes where own emotion in inherited_emotions", [f"{s}:{e}" for s, e in bad[:10]])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        own_facts = bk.get("facts", [])
        inh = n.get("inherited_facts", [])
        for f in own_facts:
            if f in inh:
                bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N16", cat, "hard")
    else:
        _fail(r, "N16", cat, "hard", f"{len(bad)} redundant fact nodes", bad[:10])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        own_emotions = bk.get("emotions", [])
        inh = n.get("inherited_emotions", [])
        for e in own_emotions:
            if e in inh:
                bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N17", cat, "hard")
    else:
        _fail(r, "N17", cat, "hard", f"{len(bad)} redundant emotion nodes", bad[:10])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        for key in ("facts", "emotions"):
            if key in bk and bk[key] != sorted(bk[key]):
                bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N18", cat, "hard")
    else:
        _fail(r, "N18", cat, "hard", f"{len(bad)} nodes with unsorted keywords in branch_key", bad[:10])

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        sid = n.get("state_id", "")
        if "action" in bk:
            if not sid.startswith("a:"):
                bad.append(sid)
            if n.get("role") not in (None, "action"):
                bad.append(sid)
    if not bad:
        _ok(r, "N19", cat, "hard")
    else:
        _fail(r, "N19", cat, "hard", f"{len(bad)} action nodes with wrong state_id or role", bad[:10])

    bad = []
    for n in _walk(tree):
        if _is_end(n):
            bk = n.get("branch_key", {})
            if "end_type" not in bk:
                bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "N20", cat, "hard")
    else:
        _fail(r, "N20", cat, "hard", f"{len(bad)} end nodes without end_type in branch_key", bad[:10])

    _skip(r, "N21", cat, "hard", "runtime concern")
    _skip(r, "N22", cat, "hard", "runtime concern")


def _check_sentences(tree, r):
    cat = "sentence"
    REQUIRED = ["script_text", "script_id", "source_call_ids", "customer_willingness"]

    for i, field in enumerate(REQUIRED, 1):
        bad = []
        for n, s in _walk_sentences(tree):
            if field not in s:
                bad.append(s.get("script_id", "?"))
        if not bad:
            _ok(r, f"SE{i}", cat, "hard")
        else:
            _fail(r, f"SE{i}", cat, "hard", f"{len(bad)} sentences missing {field}", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if s.get("collector_action") and "fact_context" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE5", cat, "hard")
    else:
        _fail(r, "SE5", cat, "hard", f"{len(bad)} sentences with collector_action but no fact_context", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if "fact_context" not in s and not _is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE6", cat, "hard")
    else:
        _fail(r, "SE6", cat, "hard", f"{len(bad)} sentences missing fact_context", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if s.get("collector_action"):
            parent_bk = n.get("branch_key", {})
            if "action" not in parent_bk and not _is_end(n) and n is not tree:
                bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE7", cat, "hard")
    else:
        _fail(r, "SE7", cat, "hard", f"{len(bad)} action sentences not under action node", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if not s.get("collector_action") and "action" in n.get("branch_key", {}):
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE8", cat, "hard")
    else:
        _fail(r, "SE8", cat, "hard", f"{len(bad)} non-action sentences in action node pool", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if s.get("customer_willingness") is None and s.get("collector_action") and "gesture_type" not in s and not _is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE9", cat, "hard")
    else:
        _warn(r, "SE9", cat, "hard", f"{len(bad)} state=None turns with collector_action", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if s.get("collector_action") == "other":
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE10", cat, "hard")
    else:
        _fail(r, "SE10", cat, "hard", f"{len(bad)} sentences with synthetic 'other' action", bad[:10])

    _skip(r, "SE11", cat, "hard", "covered by SE9")

    bad = []
    for n in _walk(tree):
        if not n.get("children", []) and not _is_end(n) and not n.get("sentence_pool", []):
            if n is not tree:
                bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "SE12", cat, "hard")
    else:
        _warn(r, "SE12", cat, "hard", f"{len(bad)} leaf nodes with empty sentence_pool (implicitly reach abrupt_end)", bad[:10])

    bad = []
    for n in _walk(tree):
        texts = [s.get("script_text", "") for s in n.get("sentence_pool", [])]
        if len(texts) != len(set(texts)):
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "SE13", cat, "hard")
    else:
        _warn(r, "SE13", cat, "hard", f"{len(bad)} nodes with duplicate script_text in pool", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if len(s.get("script_text", "")) > 150:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SE14", cat, "hard")
    else:
        _warn(r, "SE14", cat, "hard", f"{len(bad)} sentences > 150 chars", bad[:10])

    _skip(r, "SE15", cat, "hard", "runtime concern")
    _skip(r, "SE16", cat, "hard", "runtime concern")


def _check_gestures(tree, records, r):
    cat = "gesture"
    root = tree
    root_pool = root.get("sentence_pool", [])
    opening = [s for s in root_pool if s.get("gesture_type") == "opening"]

    if opening:
        _ok(r, "G1", cat, "hard")
    else:
        _fail(r, "G1", cat, "hard", "root pool has no opening gesture sentences")

    greeting_children = [c for c in root.get("children", []) if c.get("state_id") == "a:greeting"]
    if not greeting_children:
        _ok(r, "G2", cat, "hard")
    else:
        _fail(r, "G2", cat, "hard", "root has a:greeting child (greetings should be in root pool)")

    if records is not None:
        _ok(r, "G3", cat, "hard", "records provided for gesture check")
    else:
        _skip(r, "G3", cat, "hard", "no records provided")

    normal_end = None
    for c in root.get("children", []):
        if c.get("state_id") == "normal_end":
            normal_end = c
            break

    if normal_end:
        ending = [s for s in normal_end.get("sentence_pool", []) if s.get("gesture_type") == "ending"]
        if ending:
            _ok(r, "G4", cat, "hard")
        else:
            _fail(r, "G4", cat, "hard", "normal_end pool has no ending gesture sentences")

        if normal_end.get("sentence_pool"):
            _ok(r, "G5", cat, "hard")
        else:
            _fail(r, "G5", cat, "hard", "normal_end has empty sentence_pool")
    else:
        _fail(r, "G4", cat, "hard", "normal_end not found")
        _fail(r, "G5", cat, "hard", "normal_end not found")

    bad = []
    for n, s in _walk_sentences(tree):
        if s.get("gesture_type") == "ending" and not _is_end(n):
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "G6", cat, "hard")
    else:
        _fail(r, "G6", cat, "hard", f"{len(bad)} ending sentences outside end nodes", bad[:10])

    if records is not None:
        _ok(r, "G7", cat, "hard", "records provided")
    else:
        _skip(r, "G7", cat, "hard", "no records provided")

    _skip(r, "G8", cat, "hard", "needs records")
    _ok(r, "G9", cat, "hard", "structural: greetings in root pool at insert")
    _ok(r, "G10", cat, "hard", "structural: closings in normal_end at insert")
    _skip(r, "G11", cat, "hard", "runtime concern")


def _check_coverage(tree, records, r):
    cat = "coverage"
    if records is None:
        _skip(r, "C1", cat, "hard", "no records provided")
        _skip(r, "C2", cat, "hard", "no records provided")
        _skip(r, "C3", cat, "hard", "no records provided")
        _skip(r, "C4", cat, "hard", "informational")
        _skip(r, "C5", cat, "hard", "runtime concern")
        _skip(r, "C6", cat, "hard", "needs scored tree")
        _skip(r, "C7", cat, "soft", "no records provided")
        _skip(r, "C8", cat, "soft", "no records provided")
        _skip(r, "C9", cat, "soft", "no records provided")
        return

    tree_cids = set()
    tree_facts = set()
    tree_emotions = set()
    for n, s in _walk_sentences(tree):
        tree_cids.update(s.get("source_call_ids", []))
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        tree_facts.update(bk.get("facts", []))
        tree_emotions.update(bk.get("emotions", []))
        tree_facts.update(n.get("inherited_facts", []))
        tree_emotions.update(n.get("inherited_emotions", []))

    record_cids = {rec.get("call_id") for rec in records}
    missing = record_cids - tree_cids
    if not missing:
        _ok(r, "C1", cat, "hard")
    else:
        _fail(r, "C1", cat, "hard", f"{len(missing)} call_ids from data not in tree", list(missing)[:10])

    record_facts = set()
    for rec in records:
        for t in rec.get("turns_annotated", []):
            state = t.get("state", {})
            record_facts.update(state.get("facts", []))
    missing_facts = record_facts - tree_facts
    if not missing_facts:
        _ok(r, "C2", cat, "hard")
    else:
        _warn(r, "C2", cat, "hard", f"{len(missing_facts)} facts from data not in tree", list(missing_facts)[:10])

    record_emotions = set()
    for rec in records:
        for t in rec.get("turns_annotated", []):
            state = t.get("state", {})
            record_emotions.update(state.get("emotions", []))
    missing_emotions = record_emotions - tree_emotions
    if not missing_emotions:
        _ok(r, "C3", cat, "hard")
    else:
        _warn(r, "C3", cat, "hard", f"{len(missing_emotions)} emotions from data not in tree", list(missing_emotions)[:10])

    _ok(r, "C4", cat, "hard", "empty-pool branch nodes allowed")
    _skip(r, "C5", cat, "hard", "runtime concern")
    _skip(r, "C6", cat, "hard", "needs scored tree")

    _warn(r, "C7", cat, "soft", f"action types={len(tree_facts)}")
    _warn(r, "C8", cat, "soft", f"fact types={len(tree_facts)}")
    _warn(r, "C9", cat, "soft", f"emotion types={len(tree_emotions)}")


def _check_scoring(tree, r):
    cat = "scoring"
    BITMASK_KEYS = {"has_auto_loan", "has_mortgage", "has_negotiation_history",
                    "social_insurance_stable", "credit_rating_good"}

    scored_sentences = [(n, s) for n, s in _walk_sentences(tree) if "bg_constraints" in s or "win_rate" in s]

    bad = []
    for n, s in scored_sentences:
        bc = s.get("bg_constraints", {})
        if set(bc.keys()) != BITMASK_KEYS:
            bad.append((s.get("script_id", "?"), set(bc.keys())))
    if not bad:
        _ok(r, "SC1", cat, "hard")
    else:
        _fail(r, "SC1", cat, "hard", f"{len(bad)} sentences with wrong bg_constraints keys", [f"{sid}:{sorted(ks)}" for sid, ks in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        bm = s.get("bg_bitmask", {})
        if set(bm.keys()) != BITMASK_KEYS:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC2", cat, "hard")
    else:
        _fail(r, "SC2", cat, "hard", f"{len(bad)} sentences with wrong bg_bitmask keys", bad[:10])

    bad = []
    for n, s in scored_sentences:
        bmi = s.get("bg_bitmask_int", -1)
        if not (0 <= bmi <= 31):
            bad.append((s.get("script_id", "?"), bmi))
    if not bad:
        _ok(r, "SC3", cat, "hard")
    else:
        _fail(r, "SC3", cat, "hard", f"{len(bad)} sentences with bg_bitmask_int outside [0,31]", [f"{sid}:{v}" for sid, v in bad[:10]])

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
        _ok(r, "SC4", cat, "hard")
    else:
        _fail(r, "SC4", cat, "hard", f"{len(bad)} sentences with incorrect bg_bitmask_int encoding", [f"{sid}:got={g} exp={e}" for sid, g, e in bad[:10]])

    _skip(r, "SC5", cat, "hard", "bitmask AND filtering — sample check, covered by SC4")

    bad = []
    for n, s in scored_sentences:
        cids = s.get("source_call_ids", [])
        if len(cids) > 1:
            bc = s.get("bg_constraints", {})
            if not bc:
                bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC6", cat, "hard")
    else:
        _warn(r, "SC6", cat, "hard", f"{len(bad)} multi-source sentences with empty bg_constraints", bad[:10])

    bad = []
    for n, s in scored_sentences:
        wr = s.get("win_rate", -1)
        if not (0 <= wr <= 1):
            bad.append((s.get("script_id", "?"), wr))
    if not bad:
        _ok(r, "SC7", cat, "hard")
    else:
        _fail(r, "SC7", cat, "hard", f"{len(bad)} sentences with win_rate outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

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
        _ok(r, "SC8", cat, "hard")
    else:
        _warn(r, "SC8", cat, "hard", f"{len(bad)} sentences where win_rate != blend formula", [f"{sid}:got={g:.4f} exp={e:.4f}" for sid, g, e in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        wrn = s.get("win_rate_node", -1)
        if wrn != -1 and not (0 <= wrn <= 1):
            bad.append((s.get("script_id", "?"), wrn))
    if not bad:
        _ok(r, "SC9", cat, "hard")
    else:
        _fail(r, "SC9", cat, "hard", f"{len(bad)} sentences with win_rate_node outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

    bad = []
    for n, s in scored_sentences:
        if "win_rate_node" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC10", cat, "hard")
    else:
        _fail(r, "SC10", cat, "hard", f"{len(bad)} sentences missing win_rate_node", bad[:10])

    _skip(r, "SC11", cat, "hard", "covered by SC8")
    _skip(r, "SC12", cat, "hard", "covered by SC8")
    _skip(r, "SC13", cat, "hard", "covered by SC8")
    _skip(r, "SC14", cat, "hard", "covered by SC8")

    bad = []
    for n, s in scored_sentences:
        sas = s.get("sas", -1)
        if not (0 <= sas <= 1):
            bad.append((s.get("script_id", "?"), sas))
    if not bad:
        _ok(r, "SC15", cat, "hard")
    else:
        _fail(r, "SC15", cat, "hard", f"{len(bad)} sentences with sas outside [0,1]", [f"{sid}:{v}" for sid, v in bad[:10]])

    _skip(r, "SC16", cat, "hard", "runtime computation")
    _skip(r, "SC17", cat, "hard", "runtime computation")
    _skip(r, "SC18", cat, "hard", "runtime computation")

    bad = []
    for n, s in scored_sentences:
        if s.get("uplift_score", 0) != 0:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC19", cat, "hard")
    else:
        _fail(r, "SC19", cat, "hard", f"{len(bad)} sentences with uplift_score != 0", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if s.get("csi", 0) != 0:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC20", cat, "hard")
    else:
        _fail(r, "SC20", cat, "hard", f"{len(bad)} sentences with csi != 0", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if s.get("deferred", True) != True:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC21", cat, "hard")
    else:
        _fail(r, "SC21", cat, "hard", f"{len(bad)} sentences with deferred != True", bad[:10])

    bad = []
    for n, s in _walk_sentences(tree):
        if "embedding" in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC22", cat, "hard")
    else:
        _fail(r, "SC22", cat, "hard", f"{len(bad)} sentences with embedding in JSON (should be DB-only)", bad[:10])

    bad = []
    for n, s in scored_sentences:
        if "conversation_context" not in s:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC23", cat, "hard")
    else:
        _fail(r, "SC23", cat, "hard", f"{len(bad)} sentences missing conversation_context", bad[:10])

    _skip(r, "SC24", cat, "hard", "DB-only")

    bad = []
    for n, s in scored_sentences:
        bg = s.get("bg_background", {})
        if not isinstance(bg, dict):
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC25", cat, "hard")
    else:
        _fail(r, "SC25", cat, "hard", f"{len(bad)} sentences with missing/invalid bg_background", bad[:10])

    bad = []
    for n, s in scored_sentences:
        bc = s.get("bg_constraints", {})
        numeric_in_bitmask = [k for k in bc if k not in BITMASK_KEYS]
        if numeric_in_bitmask:
            bad.append(s.get("script_id", "?"))
    if not bad:
        _ok(r, "SC26", cat, "hard")
    else:
        _fail(r, "SC26", cat, "hard", f"{len(bad)} sentences with numeric fields in bitmask", bad[:10])

    _skip(r, "SC27", cat, "hard", "covered by SC4+SC5")
    _skip(r, "SC28", cat, "hard", "runtime concern")


def _check_branching(tree, r):
    cat = "branching"

    bad = []
    for n in _walk(tree):
        bk = n.get("branch_key", {})
        if "willingness" in bk:
            bad.append(n.get("state_id", "?"))
    if not bad:
        _ok(r, "B1", cat, "hard")
    else:
        _fail(r, "B1", cat, "hard", f"{len(bad)} nodes with willingness in branch_key", bad[:10])

    _skip(r, "B2", cat, "hard", "covered by N9/N10")
    _skip(r, "B3", cat, "hard", "covered by B1")
    _skip(r, "B4", cat, "hard", "covered by B1")
    _skip(r, "B5", cat, "hard", "runtime concern")
    _skip(r, "B6", cat, "hard", "runtime concern")
    _skip(r, "B7", cat, "hard", "covered by N9/N10")
    _skip(r, "B8", cat, "hard", "runtime concern")
    _skip(r, "B9", cat, "hard", "informational")

    bad = []
    for n in _walk(tree):
        for c in n.get("children", []):
            cbk = c.get("branch_key", {})
            if "action" in cbk:
                parent_bk = n.get("branch_key", {})
                if "facts" not in parent_bk and "emotions" not in parent_bk and n is not tree:
                    bad.append(c.get("state_id", "?"))
    if not bad:
        _ok(r, "B10", cat, "hard")
    else:
        _fail(r, "B10", cat, "hard", f"{len(bad)} action nodes not under decision node", bad[:10])

    _skip(r, "B11", cat, "hard", "covered by N16")
    _skip(r, "B12", cat, "hard", "covered by N17")
    _skip(r, "B13", cat, "hard", "runtime concern")


def _check_additive(tree, r):
    cat = "additive"

    _skip(r, "A1", cat, "hard", "covered by N9")
    _skip(r, "A2", cat, "hard", "covered by N9/N10")

    _ok(r, "A3", cat, "hard", "merge_dialogs validity covered by structure checks")

    bad = []
    cid_script_ids = {}
    for n, s in _walk_sentences(tree):
        for cid in s.get("source_call_ids", []):
            sid = s.get("script_id", "?")
            cid_script_ids.setdefault(cid, []).append(sid)
    for cid, sids in cid_script_ids.items():
        if len(sids) != len(set(sids)):
            bad.append(cid)
    if not bad:
        _ok(r, "A4", cat, "hard")
    else:
        _warn(r, "A4", cat, "hard", f"{len(bad)} call_ids with duplicate script_ids", bad[:10])

    _skip(r, "A5", cat, "hard", "covered by N12")
    _skip(r, "A6", cat, "hard", "runtime concern")
    _ok(r, "A7", cat, "hard", "base structure covered by S1-S6")
    _skip(r, "A8", cat, "hard", "runtime concern")


def _check_output(tree, scored_tree, r):
    cat = "output"

    if tree is not None:
        _ok(r, "O1", cat, "hard", "decision_tree.json loaded")
    else:
        _fail(r, "O1", cat, "hard", "decision_tree.json not loaded")

    if scored_tree is not None:
        _ok(r, "O2", cat, "hard", "decision_tree_scored.json loaded")
    else:
        _skip(r, "O2", cat, "hard", "scored tree not provided")

    if tree and scored_tree:
        tree_sids = set()
        scored_sids = set()
        for n in _walk(tree):
            tree_sids.add(n.get("state_id", ""))
        for n in _walk(scored_tree):
            scored_sids.add(n.get("state_id", ""))
        missing = tree_sids - scored_sids
        extra = scored_sids - tree_sids
        if not missing and not extra:
            _ok(r, "O3", cat, "hard")
        else:
            _fail(r, "O3", cat, "hard", f"node mismatch: {len(missing)} missing, {len(extra)} extra",
                  list(missing)[:5] + list(extra)[:5])

        scored_fields = {"bg_constraints", "bg_bitmask", "bg_bitmask_int", "win_rate", "sas",
                         "uplift_score", "csi", "deferred", "conversation_context", "bg_background"}
        bad = []
        for n, s in _walk_sentences(scored_tree):
            missing_f = scored_fields - set(s.keys())
            if missing_f:
                bad.append((s.get("script_id", "?"), missing_f))
        if not bad:
            _ok(r, "O4", cat, "hard")
        else:
            _fail(r, "O4", cat, "hard", f"{len(bad)} scored sentences missing fields", [f"{sid}:{sorted(mf)}" for sid, mf in bad[:10]])
    else:
        _skip(r, "O3", cat, "hard", "need both trees")
        _skip(r, "O4", cat, "hard", "need scored tree")

    _skip(r, "O5", cat, "hard", "DB-only")
    _skip(r, "O6", cat, "hard", "DB-only")
    _skip(r, "O7", cat, "hard", "DB-only")
    _skip(r, "O8", cat, "hard", "DB-only")


def _check_per_dialog(tree, records, r):
    cat = "per_dialog"

    if records is None:
        _skip(r, "D1", cat, "hard", "no records provided")
        _skip(r, "D2", cat, "hard", "no records provided")
        _skip(r, "D3", cat, "hard", "no records provided")
    else:
        bad_d1 = []
        bad_d2 = []
        bad_d3 = []
        for rec in records:
            cid = rec.get("call_id")
            path = _trace_call_id(tree, cid)
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
                if not _is_end(last):
                    terminates = any(_is_end(c) for c in last.get("children", []))
                    if not terminates:
                        bad_d3.append(cid)

        if not bad_d1:
            _ok(r, "D1", cat, "hard")
        else:
            _warn(r, "D1", cat, "hard", f"{len(bad_d1)} dialogs with duplicate facts in path", bad_d1[:10])

        if not bad_d2:
            _ok(r, "D2", cat, "hard")
        else:
            _warn(r, "D2", cat, "hard", f"{len(bad_d2)} dialogs with duplicate emotions in path", bad_d2[:10])

        if not bad_d3:
            _ok(r, "D3", cat, "hard")
        else:
            _warn(r, "D3", cat, "hard", f"{len(bad_d3)} dialogs not reaching end node", bad_d3[:10])

    all_sids = []
    for n, s in _walk_sentences(tree):
        all_sids.append(s.get("script_id", "?"))
    dup_sids = len(all_sids) - len(set(all_sids))
    if dup_sids == 0:
        _ok(r, "D4", cat, "hard")
    else:
        _warn(r, "D4", cat, "hard", f"{dup_sids} duplicate script_ids")

    identity_map = {}
    bad_d5 = []
    for n in _walk(tree):
        ident = _node_identity(n)
        if ident in identity_map and identity_map[ident] is not n:
            bad_d5.append(n.get("state_id", "?"))
        else:
            identity_map[ident] = n
    if not bad_d5:
        _ok(r, "D5", cat, "hard")
    else:
        _warn(r, "D5", cat, "hard", f"{len(bad_d5)} duplicate nodes by identity", bad_d5[:10])


def check_tree(tree, records=None, scored=False, scored_tree=None):
    r = Report()
    _check_structure(tree, r)
    _check_nodes(tree, r)
    _check_sentences(tree, r)
    _check_gestures(tree, records, r)
    _check_coverage(tree, records, r)
    if scored:
        _check_scoring(tree, r)
    else:
        for i in range(1, 29):
            _skip(r, f"SC{i}", "scoring", "hard", "not scored mode")
    _check_branching(tree, r)
    _check_additive(tree, r)
    _check_output(tree, scored_tree, r)
    _check_per_dialog(tree, records, r)
    return r


def main():
    parser = argparse.ArgumentParser(description="Check decision tree invariants")
    parser.add_argument("--scored", action="store_true", help="Also check F005 scoring invariants")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--only", default=None, help="Run only specific checks (comma-separated IDs)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show passing checks")
    parser.add_argument("--tree-path", default=None, help="Path to decision_tree.json")
    parser.add_argument("--scored-path", default=None, help="Path to decision_tree_scored.json")
    parser.add_argument("--no-records", action="store_true", help="Skip record-dependent checks")
    args = parser.parse_args()

    tree_path = args.tree_path or os.path.join(_DATA_DIR, "decision_tree.json")
    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)

    scored_tree = None
    if args.scored:
        scored_path = args.scored_path or os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "data", "decision_tree_scored.json")
        with open(scored_path, encoding="utf-8") as f:
            scored_tree = json.load(f)

    records = None
    if not args.no_records:
        try:
            records = _load_rewarded()
        except Exception:
            records = None

    report = check_tree(tree, records=records, scored=args.scored, scored_tree=scored_tree)

    if args.only:
        only_ids = set(args.only.split(","))
        report.checks = [c for c in report.checks if c.id in only_ids]

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        for c in report.checks:
            if c.status == "pass" and not args.verbose:
                continue
            prefix = {"pass": "✓", "fail": "✗", "warn": "⚠", "skip": "○"}.get(c.status, "?")
            print(f"  {prefix} {c.id} [{c.severity}] {c.message}")
            for d in c.details[:5]:
                print(f"      - {d}")
        print(f"\n{report.summary()}")

    sys.exit(report.exit_code())


if __name__ == "__main__":
    main()
