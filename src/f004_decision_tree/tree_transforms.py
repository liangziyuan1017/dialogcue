def _make_abrupt_end_node():
    return {
        "state_id": "abrupt_end",
        "branch_key": {"abrupt": True},
        "sentence_pool": [
            {
                "script_text": "[对话未正常结束]",
                "script_id": "abrupt_end_marker",
                "source_call_ids": [],
                "customer_willingness": None,
                "gesture_type": "ending",
            }
        ],
        "children": [],
        "gesture_type": "ending",
    }


def _ensure_leaf_termination(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    children = node.get("children", [])
    if not children:
        is_end = node.get("state_id") == "abrupt_end" or any(
            s.get("gesture_type") == "ending" for s in node.get("sentence_pool", [])
        )
        if not is_end:
            node["children"] = [_make_abrupt_end_node()]
    else:
        for child in children:
            _ensure_leaf_termination(child, _visited)


def _dedup_pool(pool):
    seen = set()
    result = []
    for s in pool:
        k = s.get("script_text", "")
        if k not in seen:
            seen.add(k)
            result.append(s)
    return result


def _consolidate_endpoints(root):
    normal_end = {
        "state_id": "normal_end",
        "branch_key": {"end_type": "normal"},
        "sentence_pool": [],
        "children": [],
        "gesture_type": "ending",
    }
    abrupt_end = {
        "state_id": "abrupt_end",
        "branch_key": {"end_type": "abrupt"},
        "sentence_pool": [
            {
                "script_text": "[对话未正常结束]",
                "script_id": "abrupt_end_marker",
                "source_call_ids": [],
                "customer_willingness": None,
                "gesture_type": "ending",
            }
        ],
        "children": [],
        "gesture_type": "ending",
    }

    ending_sentences = []
    _collect_ending_sentences(root, ending_sentences)
    for s in ending_sentences:
        normal_end["sentence_pool"].append(s)
    normal_end["sentence_pool"] = _dedup_pool(normal_end["sentence_pool"])
    if not normal_end["sentence_pool"]:
        normal_end["sentence_pool"].append({
            "script_text": "[正常结束]",
            "script_id": "normal_end_marker",
            "source_call_ids": [],
            "customer_willingness": None,
            "gesture_type": "ending",
        })

    _strip_terminal_nodes(root)

    root["children"].append(normal_end)
    root["children"].append(abrupt_end)


def _collect_ending_sentences(node, results, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    for s in node.get("sentence_pool", []):
        if s.get("gesture_type") == "ending" and s.get("script_text") != "[对话未正常结束]":
            results.append(s)
    for child in node.get("children", []):
        _collect_ending_sentences(child, results, _visited)


def _strip_terminal_nodes(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    children = node.get("children", [])
    to_remove = []
    for i, child in enumerate(children):
        sid = child.get("state_id", "")
        if sid == "abrupt_end" or sid == "normal_end":
            to_remove.append(i)
            continue
        _strip_terminal_nodes(child, _visited)
    for i in sorted(to_remove, reverse=True):
        _collect_ending_sentences(children[i], node.get("_ending_buf", []))
        children.pop(i)


def _ensure_abrupt_end(node, call_id, turns):
    for child in node.get("children", []):
        if child.get("state_id") == "abrupt_end":
            return
    node.setdefault("children", []).append(_make_abrupt_end_node())


def _split_composite_nodes(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    new_children = []
    for child in node.get("children", []):
        _split_composite_nodes(child, _visited)
        facts = child.get("branch_key", {}).get("facts", [])
        emotions = child.get("branch_key", {}).get("emotions", [])
        if len(facts) <= 1 and not emotions:
            new_children.append(child)
            continue
        sorted_facts = sorted(facts)
        sorted_emotions = sorted(emotions)
        chain = []
        for i, fact in enumerate(sorted_facts):
            is_last = i == len(sorted_facts) - 1
            n = {
                "state_id": f"f:{fact}",
                "branch_key": {"facts": [fact]},
                "sentence_pool": [] if not is_last else [],
                "children": [] if not is_last else [],
            }
            chain.append(n)
        if sorted_emotions:
            emotion_node = {
                "state_id": f"e:{','.join(sorted_emotions)}",
                "branch_key": {"emotions": sorted_emotions},
                "sentence_pool": child.get("sentence_pool", []),
                "children": child.get("children", []),
            }
            if chain:
                chain[-1]["children"] = [emotion_node]
            else:
                chain.append(emotion_node)
        else:
            if chain:
                chain[-1]["sentence_pool"] = child.get("sentence_pool", [])
                chain[-1]["children"] = child.get("children", [])
        for j in range(len(chain) - 1):
            if not chain[j].get("children"):
                chain[j]["children"] = [chain[j + 1]]
            else:
                chain[j]["children"].append(chain[j + 1])
        new_children.append(chain[0])
    node["children"] = new_children


def _merge_sibling_facts(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    children = node.get("children", [])
    merged = {}
    others = []
    for child in children:
        facts = child.get("branch_key", {}).get("facts", [])
        emotions = child.get("branch_key", {}).get("emotions", [])
        if len(facts) == 1 and not emotions:
            key = facts[0]
            if key not in merged:
                merged[key] = child
            else:
                existing = merged[key]
                if not existing.get("sentence_pool"):
                    existing["sentence_pool"] = child.get("sentence_pool", [])
                for c in child.get("children", []):
                    existing.setdefault("children", []).append(c)
        else:
            others.append(child)
    for child in list(merged.values()) + others:
        _merge_sibling_facts(child, _visited)
    node["children"] = list(merged.values()) + others


def _split_by_action(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    for child in node.get("children", []):
        _split_by_action(child, _visited)
    pool = node.get("sentence_pool", [])
    if not pool:
        return
    bk = node.get("branch_key", {})
    has_facts = bool(bk.get("facts"))
    has_emotions = bool(bk.get("emotions"))
    force_split = has_facts or has_emotions
    by_action = {}
    unassigned = []
    for s in pool:
        action = s.get("collector_action")
        if action:
            by_action.setdefault(action, []).append(s)
        else:
            unassigned.append(s)
    if not force_split and len(by_action) <= 1:
        return
    node["sentence_pool"] = unassigned
    action_children = []
    for action in sorted(by_action):
        action_node = {
            "state_id": f"a:{action}",
            "branch_key": {"action": action},
            "sentence_pool": by_action[action],
            "children": [],
        }
        action_children.append(action_node)
    node["children"] = action_children + node.get("children", [])


import hashlib


def _make_identity(inherited_facts, inherited_emotions, branch_key):
    bk_items = tuple(sorted(
        (k, tuple(v) if isinstance(v, list) else v) for k, v in branch_key.items()
    ))
    return (tuple(sorted(inherited_facts)), tuple(sorted(inherited_emotions)), bk_items)


def _compute_node_id(identity):
    h = hashlib.sha256(str(identity).encode()).hexdigest()[:12]
    return f"n_{h}"


def _node_identity(node):
    inherited_facts = tuple(sorted(node.get("inherited_facts", [])))
    inherited_emotions = tuple(sorted(node.get("inherited_emotions", [])))
    bk = node.get("branch_key", {})
    bk_items = tuple(sorted(
        (k, tuple(v) if isinstance(v, list) else v) for k, v in bk.items()
    ))
    return (inherited_facts, inherited_emotions, bk_items)


def _deduplicate_nodes(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    children = node.get("children", [])
    seen = {}
    merged = []
    for child in children:
        identity = _node_identity(child)
        if identity in seen:
            existing = seen[identity]
            existing.setdefault("sentence_pool", []).extend(child.get("sentence_pool", []))
            existing["sentence_pool"] = _dedup_pool(existing["sentence_pool"])
            existing.setdefault("children", []).extend(child.get("children", []))
        else:
            seen[identity] = child
            merged.append(child)
    node["children"] = merged
    for child in node["children"]:
        _deduplicate_nodes(child, _visited)


def _propagate_facts(node, accumulated_facts, accumulated_emotions=None, _visited=None):
    if _visited is None:
        _visited = set()
    if accumulated_facts is None:
        accumulated_facts = []
    if accumulated_emotions is None:
        accumulated_emotions = []
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    own_facts = node.get("branch_key", {}).get("facts", [])
    own_emotions = node.get("branch_key", {}).get("emotions", [])
    node["inherited_facts"] = list(accumulated_facts)
    node["inherited_emotions"] = list(accumulated_emotions)
    identity = _make_identity(node["inherited_facts"], node["inherited_emotions"], node.get("branch_key", {}))
    node["node_id"] = _compute_node_id(identity)
    for entry in node.get("sentence_pool", []):
        entry["fact_context"] = list(accumulated_facts)
    merged_facts = sorted(set(accumulated_facts) | set(own_facts))
    merged_emotions = sorted(set(accumulated_emotions) | set(own_emotions))
    for child in node.get("children", []):
        _propagate_facts(child, merged_facts, merged_emotions, _visited)


def _collapse_redundant_facts(node, accumulated_facts=None, accumulated_emotions=None, _visited=None):
    if accumulated_facts is None:
        accumulated_facts = set()
    if accumulated_emotions is None:
        accumulated_emotions = set()
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    own_facts = set(node.get("branch_key", {}).get("facts", []))
    own_emotions = set(node.get("branch_key", {}).get("emotions", []))
    changed = True
    while changed:
        changed = False
        new_children = []
        for child in node.get("children", []):
            child_facts = set(child.get("branch_key", {}).get("facts", []))
            child_emotions = set(child.get("branch_key", {}).get("emotions", []))
            child_action = child.get("branch_key", {}).get("action", {})
            is_redundant_fact = (
                child_facts
                and not child_emotions
                and not child_action
                and child_facts.issubset(accumulated_facts | own_facts)
            )
            is_redundant_emotion = (
                child_emotions
                and not child_facts
                and not child_action
                and child_emotions.issubset(accumulated_emotions | own_emotions)
            )
            if is_redundant_fact or is_redundant_emotion:
                parent_sentences = node.get("sentence_pool", [])
                child_sentences = child.get("sentence_pool", [])
                parent_sentences.extend(child_sentences)
                node["sentence_pool"] = _dedup_pool(parent_sentences)
                for grandchild in child.get("children", []):
                    new_children.append(grandchild)
                changed = True
            else:
                new_children.append(child)
        node["children"] = new_children
    current_facts = accumulated_facts | own_facts
    current_emotions = accumulated_emotions | own_emotions
    for child in node["children"]:
        _collapse_redundant_facts(child, current_facts, current_emotions, _visited)


def _propagate_sentences(node, parent_pool=None, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    pool = node.get("sentence_pool", [])
    if not pool and parent_pool:
        node["sentence_pool"] = list(parent_pool)
    for child in node.get("children", []):
        _propagate_sentences(child, pool if pool else parent_pool, _visited)


def _sort_keywords(node, _visited=None):
    if _visited is None:
        _visited = set()
    nid = id(node)
    if nid in _visited:
        return
    _visited.add(nid)
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            node["branch_key"][key] = sorted(node["branch_key"][key])
    for entry in node.get("sentence_pool", []):
        if "source_call_ids" in entry:
            entry["source_call_ids"] = sorted(entry["source_call_ids"])
    for child in node.get("children", []):
        _sort_keywords(child, _visited)


def _find_node_by_branch_key(node, target_key):
    if node.get("branch_key") == target_key:
        return node
    for child in node.get("children", []):
        result = _find_node_by_branch_key(child, target_key)
        if result is not None:
            return result
    return None


def _branch_key_to_str(key):
    parts = []
    if "facts" in key:
        parts.append(f"f:{','.join(key['facts'])}")
    if "emotions" in key:
        parts.append(f"e:{','.join(key['emotions'])}")
    return "|".join(parts) if parts else "no_facts_no_emotions"


def _strip_key(key, level):
    stripped = dict(key)
    if level >= 1:
        stripped.pop("emotions", None)
    if level >= 2:
        facts = stripped.get("facts", [])
        if facts:
            stripped["facts"] = facts[:-1]
    if level >= 3:
        stripped.pop("facts", None)
    return stripped


def _subset_match(node_key, target_key):
    for k, v in target_key.items():
        node_v = node_key.get(k)
        if node_v is None:
            continue
        if isinstance(v, list):
            if not all(item in node_v for item in v):
                return False
        else:
            if node_v != v:
                return False
    return True


def _search_node(node, target_key, subset=False):
    bk = node.get("branch_key", {})
    if subset:
        if _subset_match(bk, target_key):
            return node
    else:
        if bk == target_key:
            return node
    for child in node.get("children", []):
        result = _search_node(child, target_key, subset)
        if result is not None:
            return result
    return None
