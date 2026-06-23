import importlib.util
import json
import os
from collections import defaultdict

from f004_decision_tree.merge_collector import (
    CLOSING_ACTIONS, MAX_MERGED_WORDS, ACK_MAX_WORDS,
    _word_count, _is_ack_interruption, _find_merge_candidates,
    _build_merge_prompt, _enforce_word_limit, _ensure_same_action_merged,
    _llm_should_merge, _merge_turns, _apply_merges,
)
from f004_decision_tree.tree_transforms import (
    _make_abrupt_end_node, _ensure_leaf_termination, _consolidate_endpoints,
    _collect_ending_sentences, _strip_terminal_nodes, _ensure_abrupt_end,
    _split_composite_nodes, _merge_sibling_facts, _split_by_action,
    _propagate_facts, _collapse_redundant_facts, _propagate_sentences,
    _sort_keywords, _find_node_by_branch_key, _branch_key_to_str,
    _strip_key, _subset_match, _search_node,
)

def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f003_reward_labeling", "output_rewarded.py")
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
            if isinstance(v, bool):
                if v:
                    v = [list(range(len(indices)))]
                else:
                    v = [[i] for i in range(len(indices))]
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
