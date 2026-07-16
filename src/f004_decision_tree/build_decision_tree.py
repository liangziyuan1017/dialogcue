import importlib.util
import json
import os
from collections import defaultdict

from f004_decision_tree.merge_collector import (  # noqa: F401  (re-exported for tests)
    ACK_MAX_WORDS,
    CLOSING_ACTIONS,
    MAX_MERGED_WORDS,
    _apply_merges,
    _build_merge_prompt,
    _enforce_word_limit,
    _ensure_same_action_merged,
    _find_merge_candidates,
    _is_ack_interruption,
    _llm_should_merge,
    _merge_turns,
    _word_count,
)
from f004_decision_tree.tree_transforms import (  # noqa: F401  (re-exported for tests)
    _branch_key_to_str,
    _collapse_redundant_facts,
    _collect_ending_sentences,
    _compute_node_id,
    _consolidate_endpoints,
    _deduplicate_nodes,
    _ensure_abrupt_end,
    _ensure_leaf_termination,
    _find_node_by_branch_key,
    _make_abrupt_end_node,
    _make_identity,
    _merge_sibling_facts,
    _propagate_facts,
    _prune_empty_subtrees,
    _search_node,
    _sort_keywords,
    _split_by_action,
    _split_composite_nodes,
    _strip_key,
    _strip_terminal_nodes,
    _subset_match,
)
from f007_infrastructure.config import get as _cfg
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)

def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f003_reward_labeling", "data", "output_rewarded.py")
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
                if entry.get("gesture_type") and not existing_entry.get("gesture_type"):
                    existing_entry["gesture_type"] = entry["gesture_type"]
                break
        else:
            by_key[k].append(entry)
            existing.append(entry)

def _is_ancestor(node, target):
    if node is target:
        return True
    for child in node.get("children", []):
        if _is_ancestor(child, target):
            return True
    return False


def make_base_tree():
    normal_end = {
        "state_id": "normal_end",
        "branch_key": {"end_type": "normal"},
        "sentence_pool": [],
        "children": [],
        "gesture_type": "ending",
        "role": "ending",
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
        "role": "ending",
    }
    root = {
        "state_id": "initial_contact",
        "branch_key": {},
        "sentence_pool": [],
        "children": [normal_end, abrupt_end],
        "role": "opening",
    }
    return root


def build_registry_from_tree(tree):
    registry = {}
    def walk(node, acc_facts, acc_emotions):
        own_facts = node.get("branch_key", {}).get("facts", [])
        own_emotions = node.get("branch_key", {}).get("emotions", [])
        merged_facts = sorted(set(acc_facts) | set(own_facts))
        merged_emotions = sorted(set(acc_emotions) | set(own_emotions))
        if node.get("branch_key"):
            identity = _make_identity(acc_facts, acc_emotions, node.get("branch_key", {}))
            registry[identity] = node
        for child in node.get("children", []):
            walk(child, merged_facts, merged_emotions)
    walk(tree, [], [])
    return registry


def _find_or_create_child(parent, branch_key, state_id, role, identity, registry):
    for child in parent.get("children", []):
        if child.get("branch_key") == branch_key:
            return child
    node = {
        "state_id": state_id,
        "branch_key": branch_key,
        "sentence_pool": [],
        "children": [],
        "node_id": _compute_node_id(identity),
        "role": role,
    }
    parent.setdefault("children", []).append(node)
    registry[identity] = node
    return node


def _place_sentences_in_node(node, sentences, registry):
    if not sentences:
        return
    role = node.get("role", "")
    if role not in ("decision", "opening"):
        _merge_sentences(node["sentence_pool"], sentences)
        return
    by_action = {}
    unassigned = []
    for s in sentences:
        action = s.get("collector_action")
        if action:
            by_action.setdefault(action, []).append(s)
        else:
            unassigned.append(s)
    if unassigned:
        _merge_sentences(node["sentence_pool"], unassigned)
    for action in sorted(by_action):
        action_bk = {"action": action}
        action_identity = _make_identity(
            node.get("inherited_facts", []),
            node.get("inherited_emotions", []),
            action_bk,
        )
        action_child = None
        for child in node.get("children", []):
            if child.get("branch_key") == action_bk:
                action_child = child
                break
        if action_child is None:
            action_child = {
                "state_id": f"a:{action}",
                "branch_key": action_bk,
                "sentence_pool": [],
                "children": [],
                "role": "action",
            }
            node.setdefault("children", []).append(action_child)
            registry[action_identity] = action_child
        _merge_sentences(action_child["sentence_pool"], by_action[action])


def add_dialog_to_tree(tree, record, registry, merge_decisions=None):
    call_id = record.get("call_id", "")
    turns = record.get("turns_annotated", [])

    if merge_decisions is not None:
        turns = _apply_merges(turns, call_id, merge_decisions)

    normal_end = None
    for child in tree.get("children", []):
        if child.get("state_id") == "normal_end":
            normal_end = child
            break

    has_closing = False

    segments = _extract_segments(turns, call_id)

    current_node = tree
    accumulated_facts = []
    accumulated_emotions = []

    for seg in segments:
        branch_key = seg["branch_key"]
        seg_facts = branch_key.get("facts", [])
        seg_emotions = branch_key.get("emotions", [])

        if seg.get("is_closing"):
            has_closing = True
            for s in seg["sentences"]:
                s["gesture_type"] = "ending"
            if branch_key:
                for fact in seg_facts:
                    if fact in accumulated_facts:
                        continue
                    single_bk = {"facts": [fact]}
                    child_identity = _make_identity(accumulated_facts, accumulated_emotions, single_bk)
                    if child_identity in registry:
                        matching = registry[child_identity]
                        if not _is_ancestor(matching, current_node):
                            children = current_node.setdefault("children", [])
                            if matching not in children:
                                children.append(matching)
                        current_node = matching
                        accumulated_facts = sorted(set(accumulated_facts) | {fact})
                        continue
                    current_node = _find_or_create_child(
                        current_node, single_bk, f"f:{fact}", "decision", child_identity, registry
                    )
                    accumulated_facts = sorted(set(accumulated_facts) | {fact})
                for emotion in seg_emotions:
                    if emotion in accumulated_emotions:
                        continue
                    single_bk = {"emotions": [emotion]}
                    child_identity = _make_identity(accumulated_facts, accumulated_emotions, single_bk)
                    if child_identity in registry:
                        matching = registry[child_identity]
                        if not _is_ancestor(matching, current_node):
                            children = current_node.setdefault("children", [])
                            if matching not in children:
                                children.append(matching)
                        current_node = matching
                        accumulated_emotions = sorted(set(accumulated_emotions) | {emotion})
                        continue
                    current_node = _find_or_create_child(
                        current_node, single_bk, f"e:{emotion}", "decision", child_identity, registry
                    )
                    accumulated_emotions = sorted(set(accumulated_emotions) | {emotion})
            if normal_end is not None:
                _place_sentences_in_node(current_node, seg["sentences"], registry)
            continue

        if not branch_key:
            _place_sentences_in_node(current_node, seg["sentences"], registry)
        else:
            for fact in seg_facts:
                if fact in accumulated_facts:
                    continue
                single_bk = {"facts": [fact]}
                child_identity = _make_identity(accumulated_facts, accumulated_emotions, single_bk)

                if child_identity in registry:
                    matching = registry[child_identity]
                    if not _is_ancestor(matching, current_node):
                        children = current_node.setdefault("children", [])
                        if matching not in children:
                            children.append(matching)
                    current_node = matching
                    accumulated_facts = sorted(set(accumulated_facts) | {fact})
                    continue

                current_node = _find_or_create_child(
                    current_node, single_bk, f"f:{fact}", "decision", child_identity, registry
                )
                accumulated_facts = sorted(set(accumulated_facts) | {fact})

            for emotion in seg_emotions:
                if emotion in accumulated_emotions:
                    continue
                single_bk = {"emotions": [emotion]}
                child_identity = _make_identity(accumulated_facts, accumulated_emotions, single_bk)

                if child_identity in registry:
                    matching = registry[child_identity]
                    if not _is_ancestor(matching, current_node):
                        children = current_node.setdefault("children", [])
                        if matching not in children:
                            children.append(matching)
                    current_node = matching
                    accumulated_emotions = sorted(set(accumulated_emotions) | {emotion})
                    continue

                current_node = _find_or_create_child(
                    current_node, single_bk, f"e:{emotion}", "decision", child_identity, registry
                )
                accumulated_emotions = sorted(set(accumulated_emotions) | {emotion})

            _place_sentences_in_node(current_node, seg["sentences"], registry)

    if not has_closing and normal_end is not None:
        pass


def _get_abrupt_end(tree):
    for child in tree.get("children", []):
        if child.get("state_id") == "abrupt_end":
            return child
    return None


def merge_dialogs(tree_path, new_records, merge_decisions=None):
    tree = None
    if os.path.exists(tree_path):
        try:
            with open(tree_path, encoding="utf-8") as f:
                tree = json.load(f)
        except (json.JSONDecodeError, ValueError):
            tree = None
    if tree is None:
        tree = make_base_tree()
        registry = {}
    else:
        registry = build_registry_from_tree(tree)
    for record in new_records:
        add_dialog_to_tree(tree, record, registry, merge_decisions=merge_decisions)
    _propagate_facts(tree, [], [])
    _deduplicate_nodes(tree)
    _prune_empty_subtrees(tree)
    _consolidate_endpoints(tree)
    _sort_keywords(tree)
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    return tree


def build_tree(records, merge_decisions=None):
    tree = make_base_tree()
    registry = {}
    for record in records:
        add_dialog_to_tree(tree, record, registry, merge_decisions=merge_decisions)
    _propagate_facts(tree, [], [])
    _prune_empty_subtrees(tree)
    _consolidate_endpoints(tree)
    _sort_keywords(tree)
    return tree

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

    for level in range(1, _cfg("decision_tree.find_node_max_levels", 4)):
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
    cache_path = os.path.join(os.path.dirname(__file__), "data", "merge_decisions.json")
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
    cache_path = os.path.join(os.path.dirname(__file__), "data", "merge_decisions.json")
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
        output_path = os.path.join(os.path.dirname(__file__), "data", "decision_tree.json")

    merge_cache = _load_merge_cache()
    tree = make_base_tree()
    registry = {}
    for record in records:
        add_dialog_to_tree(tree, record, registry, merge_decisions=merge_cache)
    _save_merge_cache(merge_cache)
    _propagate_facts(tree, [], [])
    _deduplicate_nodes(tree)
    _prune_empty_subtrees(tree)
    _consolidate_endpoints(tree)
    _sort_keywords(tree)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    return _count_nodes(tree)

def write_dialog_records(records, output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "dialog_records.json")
    dialog_records = []
    for record in records:
        turns = []
        for turn in record.get("turns_annotated", []):
            state = turn.get("state") or {}
            entry = {
                "turn_index": turn.get("turn_index"),
                "role": turn.get("role"),
                "text": turn.get("text", ""),
            }
            if state:
                entry["action"] = state.get("action")
                entry["facts"] = state.get("facts", [])
                entry["emotions"] = state.get("emotions", [])
                entry["willingness"] = state.get("willingness")
            turns.append(entry)
        dialog_records.append({"call_id": record.get("call_id"), "turns": turns})
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dialog_records, f, indent=2, ensure_ascii=False)
    return len(dialog_records)

def write_dialog_records_incremental(new_records, output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "dialog_records.json")
    existing = []
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
    existing_ids = {r.get("call_id") for r in existing}
    for record in new_records:
        call_id = record.get("call_id")
        if call_id in existing_ids:
            continue
        turns = []
        for turn in record.get("turns_annotated", []):
            state = turn.get("state") or {}
            entry = {
                "turn_index": turn.get("turn_index"),
                "role": turn.get("role"),
                "text": turn.get("text", ""),
            }
            if state:
                entry["action"] = state.get("action")
                entry["facts"] = state.get("facts", [])
                entry["emotions"] = state.get("emotions", [])
                entry["willingness"] = state.get("willingness")
            turns.append(entry)
        existing.append({"call_id": call_id, "turns": turns})
        existing_ids.add(call_id)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    return len(existing)

def _count_nodes(node, visited=None):
    if visited is None:
        visited = set()
    node_id = id(node)
    if node_id in visited:
        return 0
    visited.add(node_id)
    count = 1
    for child in node.get("children", []):
        count += _count_nodes(child, visited)
    return count

if __name__ == "__main__":
    count = write_decision_tree()
    _log.info(f"Wrote decision tree with {count} nodes to decision_tree.json")
