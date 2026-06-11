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


def _make_state_key(state):
    key = {}
    if "facts" in state and state["facts"]:
        key["facts"] = sorted(state["facts"])
    if "emotions" in state and state["emotions"]:
        key["emotions"] = sorted(state["emotions"])
    if "willingness" in state and state["willingness"]:
        key["willingness"] = state["willingness"]
    if "action" in state and state["action"]:
        key["action"] = state["action"]
    return key


def _state_key_to_str(key):
    parts = []
    if "action" in key:
        parts.append(f"a:{key['action']}")
    if "willingness" in key:
        parts.append(f"w:{key['willingness']}")
    if "facts" in key:
        parts.append(f"f:{','.join(key['facts'])}")
    if "emotions" in key:
        parts.append(f"e:{','.join(key['emotions'])}")
    return "|".join(parts) if parts else "unknown"


def extract_state_paths(record):
    turns = record.get("turns_annotated", [])
    call_id = record.get("call_id", "")
    paths = []
    collector_sentences = []

    initial_key = {"action": "greeting"}
    paths.append((initial_key, None))

    for turn in turns:
        state = turn.get("state")
        if state and turn["role"] == "催收员":
            key = _make_state_key(state)
            paths.append((key, turn["text"]))
            collector_sentences.append({
                "script_text": turn["text"],
                "script_id": f"{call_id}_t{turn['turn_index']}",
                "source_call_ids": [call_id],
            })
        elif state and turn["role"] == "客户":
            key = _make_state_key(state)
            paths.append((key, None))

    return paths


def _merge_sentences(existing, new_entries):
    by_text = defaultdict(list)
    for entry in existing:
        by_text[entry["script_text"]].append(entry)

    for entry in new_entries:
        text = entry["script_text"]
        if text in by_text:
            for existing_entry in by_text[text]:
                for cid in entry["source_call_ids"]:
                    if cid not in existing_entry["source_call_ids"]:
                        existing_entry["source_call_ids"].append(cid)
                        existing_entry["source_call_ids"].sort()
        else:
            by_text[text].append(entry)
            existing.append(entry)


def _insert_path(node, path_steps, call_id, depth=0):
    if not path_steps:
        return

    state_key, collector_text = path_steps[0]
    state_str = _state_key_to_str(state_key)
    state_id = state_str if depth > 0 else "initial_contact"

    children = node.setdefault("children", [])
    matching = None
    for child in children:
        if child.get("state_key") == state_key:
            matching = child
            break

    if matching is None:
        matching = {
            "state_id": state_id,
            "state_key": state_key,
            "sentence_pool": [],
            "children": [],
        }
        children.append(matching)

    if collector_text:
        entry = {
            "script_text": collector_text,
            "script_id": f"{call_id}_d{depth}",
            "source_call_ids": [call_id],
        }
        _merge_sentences(matching["sentence_pool"], [entry])

    _insert_path(matching, path_steps[1:], call_id, depth + 1)


def build_tree(records):
    root = {
        "state_id": "initial_contact",
        "state_key": {"action": "greeting"},
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
                }
                _merge_sentences(root["sentence_pool"], [entry])
                break

        path_steps = []
        current_key = None
        for turn in turns:
            state = turn.get("state")
            if not state:
                continue
            key = _make_state_key(state)
            if key != current_key:
                if turn["role"] == "催收员":
                    path_steps.append((key, turn["text"]))
                else:
                    path_steps.append((key, None))
                current_key = key

        if path_steps:
            _insert_path(root, path_steps, call_id)

    _propagate_sentences(root)
    _sort_keywords(root)
    return root


def _propagate_sentences(node, parent_pool=None):
    pool = node.get("sentence_pool", [])
    if not pool and parent_pool:
        node["sentence_pool"] = list(parent_pool)
    for child in node.get("children", []):
        _propagate_sentences(child, pool if pool else parent_pool)


def _sort_keywords(node):
    for key in ("facts", "emotions"):
        if key in node.get("state_key", {}):
            node["state_key"][key] = sorted(node["state_key"][key])
    for entry in node.get("sentence_pool", []):
        for cid_key in ("source_call_ids",):
            if cid_key in entry:
                entry[cid_key] = sorted(entry[cid_key])
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
    if level >= 4:
        stripped.pop("willingness", None)
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
    if subset:
        if _subset_match(node.get("state_key", {}), target_key):
            return node
    else:
        if node.get("state_key") == target_key:
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

    for level in range(1, 5):
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
