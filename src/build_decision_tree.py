import importlib.util
import json
import os
from collections import defaultdict


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
        k = (entry["script_text"], entry.get("customer_willingness"))
        by_key[k].append(entry)

    for entry in new_entries:
        k = (entry["script_text"], entry.get("customer_willingness"))
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


def build_tree(records):
    root = {
        "state_id": "initial_contact",
        "branch_key": {},
        "sentence_pool": [],
        "children": [],
    }

    for record in records:
        call_id = record.get("call_id", "")
        turns = record.get("turns_annotated", [])

        for turn in turns:
            if turn["role"] == "催收员" and turn.get("state", {}).get("action") == "greeting":
                entry = {
                    "script_text": turn["text"],
                    "script_id": f"{call_id}_t{turn['turn_index']}",
                    "source_call_ids": [call_id],
                    "customer_willingness": None,
                }
                _merge_sentences(root["sentence_pool"], [entry])
                break

        segments = _extract_segments(turns, call_id)

        current_node = root
        for seg in segments:
            branch_key = seg["branch_key"]
            branch_str = _branch_key_to_str(branch_key)

            children = current_node.setdefault("children", [])
            matching = None
            for child in children:
                if child.get("branch_key") == branch_key:
                    matching = child
                    break

            if matching is None:
                matching = {
                    "state_id": branch_str,
                    "branch_key": branch_key,
                    "sentence_pool": [],
                    "children": [],
                }
                children.append(matching)

            _merge_sentences(matching["sentence_pool"], seg["sentences"])
            current_node = matching

    _propagate_sentences(root)
    _sort_keywords(root)
    return root


def _extract_segments(turns, call_id):
    segments = []
    current_branch_key = None
    current_sentences = []
    last_willingness = None

    for turn in turns:
        state = turn.get("state")
        if not state:
            continue

        if turn["role"] == "客户":
            new_branch_key = _make_branch_key(state)
            last_willingness = state.get("willingness")

            if new_branch_key != current_branch_key:
                if current_branch_key is not None and current_sentences:
                    segments.append({
                        "branch_key": current_branch_key,
                        "sentences": current_sentences,
                    })
                current_branch_key = new_branch_key
                current_sentences = []

        elif turn["role"] == "催收员":
            action = state.get("action")
            if action and current_branch_key is not None:
                entry = {
                    "script_text": turn["text"],
                    "script_id": f"{call_id}_t{turn['turn_index']}",
                    "source_call_ids": [call_id],
                    "customer_willingness": last_willingness,
                }
                current_sentences.append(entry)

    if current_branch_key is not None and current_sentences:
        segments.append({
            "branch_key": current_branch_key,
            "sentences": current_sentences,
        })

    return segments


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


def write_decision_tree(records=None, output_path=None):
    if records is None:
        records = _load_rewarded()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "decision_tree.json")

    tree = build_tree(records)

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
