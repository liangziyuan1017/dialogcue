import importlib.util
import json
import os
import re
from collections import defaultdict


CLOSING_ACTIONS = {"closure", "goodbye"}


def _word_count(text):
    cleaned = re.sub(r"[，。、！？；：\u201c\u201d\u2018\u2019（）\s]", "", text)
    return len(cleaned)


def _find_merge_candidates(turns):
    candidates = []
    i = 0
    while i < len(turns):
        if turns[i]["role"] == "催收员":
            group_indices = [i]
            interruptions = []
            j = i + 1
            while j < len(turns):
                if turns[j]["role"] == "催收员":
                    group_indices.append(j)
                    j += 1
                elif turns[j]["role"] == "客户" and _word_count(turns[j]["text"]) < 6:
                    if j + 1 < len(turns) and turns[j + 1]["role"] == "催收员":
                        interruptions.append(j)
                        j += 1
                    else:
                        break
                else:
                    break
            if len(group_indices) >= 2:
                candidates.append({
                    "collector_indices": group_indices,
                    "interruption_indices": interruptions,
                })
            i = j
        else:
            i += 1
    return candidates


def _build_merge_prompt(turns, group):
    parts = []
    for idx in group["collector_indices"]:
        parts.append(f"催收员: {turns[idx]['text']}")
    for idx in group["interruption_indices"]:
        parts.insert(
            group["collector_indices"].index(
                next(c for c in group["collector_indices"] if c > idx)
            ),
            f"客户: {turns[idx]['text']}",
        )
    dialog_text = "\n".join(f"催收员: {turns[i]['text']}" for i in group["collector_indices"])
    interruptions_text = ""
    if group["interruption_indices"]:
        interruptions_text = "\n".join(
            f"[客户说: {turns[i]['text']}]" for i in group["interruption_indices"]
        )
    prompt = f"""判断以下催收员的连续话语是否应该合并为一个完整表述。

重要：默认应KEEP。只有当你非常确定这些话语是同一个未说完的句子被客户打断后继续时才MERGE。如果有任何犹豫，选择KEEP。

催收员话语:
{dialog_text}
{interruptions_text}

合并规则 (偏向KEEP，只有明确是同一话题才MERGE):
- 如果这些话语明确在延续同一个方案解释或同一个论点论证 → MERGE
- 如果客户只是简短应答(嗯/好)而催收员接着说同一方案的下一句 → MERGE
- 如果催收员在不同客户回应后转向了不同论点 → KEEP
- 如果客户提出了新的观点或异议 → KEEP
- 如果话语之间有客户实质性插话(提问/反驳/新信息) → KEEP
- 如果不确定 → KEEP

回复JSON:
{{"decision": "MERGE或KEEP", "reason": "简要说明"}}"""
    return prompt


def _llm_should_merge(turns, group):
    from llm_client import call_deepseek_json
    from retry import retry_call
    prompt = _build_merge_prompt(turns, group)
    result = retry_call(call_deepseek_json, prompt)
    decision = result.get("decision", "KEEP").upper()
    return decision == "MERGE", result.get("reason", "")


def _merge_turns(turns, group, call_id):
    indices = group["collector_indices"]
    first = turns[indices[0]]
    merged_text = " ".join(turns[i]["text"] for i in indices)
    actions = []
    for i in indices:
        action = (turns[i].get("state") or {}).get("action")
        if action:
            actions.append(action)
    primary_action = actions[0] if actions else None
    last_willingness = None
    for i in reversed(indices):
        w = (turns[i].get("state") or {}).get("willingness")
        if w:
            last_willingness = w
            break
    merged_ids = [f"{call_id}_t{turns[i]['turn_index']}" for i in indices]
    entry = {
        "script_text": merged_text,
        "script_id": f"{call_id}_t{first['turn_index']}_merged",
        "source_call_ids": [call_id],
        "customer_willingness": last_willingness,
        "merged_from": merged_ids,
    }
    if primary_action:
        entry["collector_action"] = primary_action
    return entry


def _apply_merges(turns, call_id, merge_decisions=None):
    candidates = _find_merge_candidates(turns)
    if not candidates:
        return turns
    remove_indices = set()
    merge_entries = {}
    for group in candidates:
        key = tuple(group["collector_indices"])
        cache_key = (call_id, key)
        if merge_decisions is not None and cache_key in merge_decisions:
            should_merge = merge_decisions[cache_key]
        else:
            should_merge, _ = _llm_should_merge(turns, group)
            if merge_decisions is not None:
                merge_decisions[cache_key] = should_merge
        if should_merge:
            first_idx = group["collector_indices"][0]
            merge_entries[first_idx] = _merge_turns(turns, group, call_id)
            for idx in group["collector_indices"][1:]:
                remove_indices.add(idx)
            for idx in group["interruption_indices"]:
                state = turns[idx].get("state") or {}
                if not state.get("facts") and not state.get("emotions"):
                    remove_indices.add(idx)
    result = []
    for i, turn in enumerate(turns):
        if i in remove_indices:
            continue
        if i in merge_entries:
            merged = merge_entries[i]
            result.append({
                "turn_index": turn["turn_index"],
                "role": "催收员",
                "text": merged["script_text"],
                "state": turn.get("state", {}),
                "_merged_entry": merged,
            })
        else:
            result.append(turn)
    return result


def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _make_branch_key(state):
    key = {}
    facts = state.get("facts", [])
    emotions = state.get("emotions", [])
    if facts:
        key["facts"] = sorted(facts)
    if emotions:
        key["emotions"] = sorted(emotions)
    return key


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


def extract_state_paths(record):
    turns = record.get("turns_annotated", [])
    call_id = record.get("call_id", "")
    paths = []
    last_customer_willingness = None

    for turn in turns:
        state = turn.get("state")
        if not state:
            continue
        if turn["role"] == "催收员":
            action = state.get("action")
            if action:
                entry = {
                    "type": "collector",
                    "action": action,
                    "sentence": {
                        "script_text": turn["text"],
                        "script_id": f"{call_id}_t{turn['turn_index']}",
                        "source_call_ids": [call_id],
                        "customer_willingness": last_customer_willingness,
                    },
                }
                paths.append(entry)
        elif turn["role"] == "客户":
            branch_key = _make_branch_key(state)
            last_customer_willingness = state.get("willingness")
            entry = {
                "type": "customer",
                "branch_key": branch_key,
                "willingness": last_customer_willingness,
            }
            paths.append(entry)

    return paths


def _merge_sentences(existing, new_entries):
    by_key = defaultdict(list)
    for entry in existing:
        k = (entry["script_text"], entry.get("customer_willingness"), entry.get("collector_action"))
        by_key[k].append(entry)

    for entry in new_entries:
        k = (entry["script_text"], entry.get("customer_willingness"), entry.get("collector_action"))
        if k in by_key:
            for existing_entry in by_key[k]:
                for cid in entry["source_call_ids"]:
                    if cid not in existing_entry["source_call_ids"]:
                        existing_entry["source_call_ids"].append(cid)
                        existing_entry["source_call_ids"].sort()
                break
        else:
            by_key[k].append(entry)
            existing.append(entry)


def build_tree(records, merge_decisions=None):
    root = {
        "state_id": "initial_contact",
        "branch_key": {},
        "sentence_pool": [],
        "children": [],
    }

    for record in records:
        call_id = record.get("call_id", "")
        turns = record.get("turns_annotated", [])

        if merge_decisions is not None:
            turns = _apply_merges(turns, call_id, merge_decisions)

        has_closing = False

        for turn in turns:
            if turn["role"] == "催收员" and turn.get("state", {}).get("action") == "greeting":
                entry = {
                    "script_text": turn["text"],
                    "script_id": f"{call_id}_t{turn['turn_index']}",
                    "source_call_ids": [call_id],
                    "customer_willingness": None,
                    "gesture_type": "opening",
                    "collector_action": "greeting",
                }
                _merge_sentences(root["sentence_pool"], [entry])

        segments = _extract_segments(turns, call_id)

        current_node = root
        for seg in segments:
            branch_key = seg["branch_key"]
            seg_facts = branch_key.get("facts", [])
            seg_emotions = branch_key.get("emotions", [])

            if not branch_key:
                _merge_sentences(current_node["sentence_pool"], seg["sentences"])
            else:
                for fact in seg_facts:
                    single_bk = {"facts": [fact]}
                    children = current_node.setdefault("children", [])
                    matching = None
                    for child in children:
                        if child.get("branch_key") == single_bk:
                            matching = child
                            break
                    if matching is None:
                        matching = {
                            "state_id": f"f:{fact}",
                            "branch_key": single_bk,
                            "sentence_pool": [],
                            "children": [],
                        }
                        children.append(matching)
                    current_node = matching

                for emotion in seg_emotions:
                    single_bk = {"emotions": [emotion]}
                    children = current_node.setdefault("children", [])
                    matching = None
                    for child in children:
                        if child.get("branch_key") == single_bk:
                            matching = child
                            break
                    if matching is None:
                        matching = {
                            "state_id": f"e:{emotion}",
                            "branch_key": single_bk,
                            "sentence_pool": [],
                            "children": [],
                        }
                        children.append(matching)
                    current_node = matching

                _merge_sentences(current_node["sentence_pool"], seg["sentences"])

            if seg.get("is_closing"):
                has_closing = True
                for s in seg["sentences"]:
                    s["gesture_type"] = "ending"

        if not has_closing:
            _ensure_abrupt_end(current_node, call_id, turns)

    _propagate_sentences(root)
    _sort_keywords(root)
    _ensure_leaf_termination(root)
    _consolidate_endpoints(root)
    return root


def _extract_segments(turns, call_id):
    segments = []
    current_branch_key = {}
    current_sentences = []
    last_willingness = None
    is_closing = False

    for turn in turns:
        state = turn.get("state")

        if turn["role"] == "客户":
            new_branch_key = _make_branch_key(state or {})
            last_willingness = (state or {}).get("willingness")

            if new_branch_key and new_branch_key != current_branch_key:
                segments.append({
                    "branch_key": current_branch_key,
                    "sentences": current_sentences,
                    "is_closing": is_closing,
                })
                current_branch_key = new_branch_key
                current_sentences = []
                is_closing = False

        elif turn["role"] == "催收员":
            if turn.get("_merged_entry"):
                entry = dict(turn["_merged_entry"])
                entry["customer_willingness"] = last_willingness
                current_sentences.append(entry)
                action = entry.get("collector_action")
            else:
                action = (state or {}).get("action")
                if action == "greeting":
                    continue
                entry = {
                    "script_text": turn["text"],
                    "script_id": f"{call_id}_t{turn['turn_index']}",
                    "source_call_ids": [call_id],
                    "customer_willingness": last_willingness,
                }
                if action:
                    entry["collector_action"] = action
                current_sentences.append(entry)
            if action in CLOSING_ACTIONS:
                is_closing = True

    segments.append({
        "branch_key": current_branch_key,
        "sentences": current_sentences,
        "is_closing": is_closing,
    })

    return segments


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


def _ensure_leaf_termination(node):
    children = node.get("children", [])
    if not children:
        is_end = node.get("state_id") == "abrupt_end" or any(
            s.get("gesture_type") == "ending" for s in node.get("sentence_pool", [])
        )
        if not is_end:
            node["children"] = [_make_abrupt_end_node()]
    else:
        for child in children:
            _ensure_leaf_termination(child)


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


def _collect_ending_sentences(node, results):
    for s in node.get("sentence_pool", []):
        if s.get("gesture_type") == "ending" and s.get("script_text") != "[对话未正常结束]":
            results.append(s)
    for child in node.get("children", []):
        _collect_ending_sentences(child, results)


def _strip_terminal_nodes(node):
    children = node.get("children", [])
    to_remove = []
    for i, child in enumerate(children):
        sid = child.get("state_id", "")
        if sid == "abrupt_end" or sid == "normal_end":
            to_remove.append(i)
            continue
        _strip_terminal_nodes(child)
    for i in sorted(to_remove, reverse=True):
        _collect_ending_sentences(children[i], node.get("_ending_buf", []))
        children.pop(i)


def _ensure_abrupt_end(node, call_id, turns):
    for child in node.get("children", []):
        if child.get("state_id") == "abrupt_end":
            return
    node.setdefault("children", []).append(_make_abrupt_end_node())


def _split_composite_nodes(node):
    new_children = []
    for child in node.get("children", []):
        _split_composite_nodes(child)
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


def _merge_sibling_facts(node):
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
        _merge_sibling_facts(child)
    node["children"] = list(merged.values()) + others


def _split_by_action(node):
    for child in node.get("children", []):
        _split_by_action(child)
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


def _propagate_facts(node, accumulated_facts):
    own_facts = node.get("branch_key", {}).get("facts", [])
    node["inherited_facts"] = list(accumulated_facts)
    for entry in node.get("sentence_pool", []):
        entry["fact_context"] = list(accumulated_facts)
    merged = sorted(set(accumulated_facts) | set(own_facts))
    for child in node.get("children", []):
        _propagate_facts(child, merged)


def _collapse_redundant_facts(node, accumulated_facts=None):
    if accumulated_facts is None:
        accumulated_facts = set()
    own_facts = set(node.get("branch_key", {}).get("facts", []))
    changed = True
    while changed:
        changed = False
        new_children = []
        for child in node.get("children", []):
            child_facts = set(child.get("branch_key", {}).get("facts", []))
            child_emotions = child.get("branch_key", {}).get("emotions", [])
            child_action = child.get("branch_key", {}).get("action", {})
            is_redundant_fact = (
                child_facts
                and not child_emotions
                and not child_action
                and child_facts.issubset(accumulated_facts | own_facts)
            )
            if is_redundant_fact:
                parent_sentences = node.get("sentence_pool", [])
                child_sentences = child.get("sentence_pool", [])
                parent_sentences.extend(child_sentences)
                for grandchild in child.get("children", []):
                    new_children.append(grandchild)
                changed = True
            else:
                new_children.append(child)
        node["children"] = new_children
    current_facts = accumulated_facts | own_facts
    for child in node["children"]:
        _collapse_redundant_facts(child, current_facts)


def _propagate_sentences(node, parent_pool=None):
    pool = node.get("sentence_pool", [])
    if not pool and parent_pool:
        node["sentence_pool"] = list(parent_pool)
    for child in node.get("children", []):
        _propagate_sentences(child, pool if pool else parent_pool)


def _sort_keywords(node):
    for key in ("facts", "emotions"):
        if key in node.get("branch_key", {}):
            node["branch_key"][key] = sorted(node["branch_key"][key])
    for entry in node.get("sentence_pool", []):
        if "source_call_ids" in entry:
            entry["source_call_ids"] = sorted(entry["source_call_ids"])
    for child in node.get("children", []):
        _sort_keywords(child)


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


def find_node(tree, state_key):
    result = _search_node(tree, state_key)
    if result is not None:
        return result

    for level in range(1, 4):
        stripped = _strip_key(state_key, level)
        if not stripped:
            break
        result = _search_node(tree, stripped)
        if result is not None:
            return result
        result = _search_node(tree, stripped, subset=True)
        if result is not None:
            return result

    return None


def _load_merge_cache():
    cache_path = os.path.join(os.path.dirname(__file__), "merge_decisions.json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            raw = json.load(f)
        cache = {}
        for k, v in raw.items():
            parts = k.split(":")
            call_id = parts[0]
            indices = tuple(int(x) for x in parts[1].split(","))
            cache[(call_id, indices)] = v
        return cache
    return {}


def _save_merge_cache(cache):
    cache_path = os.path.join(os.path.dirname(__file__), "merge_decisions.json")
    raw = {}
    for (call_id, indices), decision in cache.items():
        key = f"{call_id}:{','.join(str(i) for i in indices)}"
        raw[key] = decision
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def write_decision_tree(records=None, output_path=None):
    if records is None:
        records = _load_rewarded()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "decision_tree.json")

    merge_cache = _load_merge_cache()
    tree = build_tree(records, merge_decisions=merge_cache)
    _save_merge_cache(merge_cache)
    _split_composite_nodes(tree)
    _merge_sibling_facts(tree)
    _collapse_redundant_facts(tree)
    _split_by_action(tree)
    _propagate_facts(tree, [])

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    return _count_nodes(tree)


def _count_nodes(node):
    count = 1
    for child in node.get("children", []):
        count += _count_nodes(child)
    return count


if __name__ == "__main__":
    count = write_decision_tree()
    print(f"Wrote decision tree with {count} nodes to decision_tree.json")
