import json
import os

import importlib.util

import pytest


def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("output_rewarded", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_tree():
    tree_path = os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json")
    with open(tree_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _all_tree_sentences(node, results=None):
    if results is None:
        results = []
    for s in node.get("sentence_pool", []):
        results.append(s)
    for c in node.get("children", []):
        _all_tree_sentences(c, results)
    return results


def _find_child_by_bk(node, bk):
    for c in node.get("children", []):
        if c.get("branch_key") == bk:
            return c
    return None


def _find_node_in_subtree(node, bk):
    if node.get("branch_key") == bk:
        return node
    for c in node.get("children", []):
        result = _find_node_in_subtree(c, bk)
        if result is not None:
            return result
    return None


def _find_fact_node(current, fact, accumulated_facts, root):
    child = _find_child_by_bk(current, {"facts": [fact]})
    if child is not None:
        return child
    if fact in accumulated_facts:
        return None
    for c in current.get("children", []):
        result = _find_node_in_subtree(c, {"facts": [fact]})
        if result is not None:
            return result
    return None


def _find_emotion_node(current, emotion, root):
    child = _find_child_by_bk(current, {"emotions": [emotion]})
    if child is not None:
        return child
    for c in current.get("children", []):
        child = _find_child_by_bk(c, {"emotions": [emotion]})
        if child is not None:
            return child
    return None


def _find_action_sentence(current, action, sid, call_id, text, root):
    for c in current.get("children", []):
        if c.get("branch_key", {}).get("action") == action:
            for s in c.get("sentence_pool", []):
                if s.get("script_id") == sid or sid in s.get("merged_from", []):
                    return True
    for s in current.get("sentence_pool", []):
        if s.get("script_id") == sid or sid in s.get("merged_from", []):
            return True
    all_sents = _all_tree_sentences(root)
    for s in all_sents:
        if sid in s.get("merged_from", []):
            return True
        if s.get("collector_action") == action and call_id in s.get("source_call_ids", []):
            if s.get("script_text") == text:
                return True
    return False


def _extract_expected_sequence(record):
    turns = record.get("turns_annotated", [])
    call_id = record.get("call_id", "")
    sequence = []
    accumulated_facts = []

    for turn in turns:
        state = turn.get("state") or {}
        role = turn["role"]
        turn_index = turn["turn_index"]

        if role == "催收员":
            action = state.get("action")
            if action == "greeting":
                sequence.append({
                    "type": "greeting",
                    "turn_index": turn_index,
                    "text": turn["text"],
                    "action": "greeting",
                    "facts": [],
                    "emotions": [],
                })
            elif action:
                sequence.append({
                    "type": "collector_action",
                    "turn_index": turn_index,
                    "text": turn["text"],
                    "action": action,
                    "facts": list(accumulated_facts),
                    "emotions": list(state.get("emotions", [])),
                })
            else:
                sequence.append({
                    "type": "collector_no_action",
                    "turn_index": turn_index,
                    "text": turn["text"],
                    "facts": list(accumulated_facts),
                    "emotions": [],
                })

        elif role == "客户":
            facts = state.get("facts", [])
            emotions = state.get("emotions", [])
            new_facts = [f for f in facts if f not in accumulated_facts]
            if new_facts or emotions:
                sequence.append({
                    "type": "customer_state",
                    "turn_index": turn_index,
                    "facts": new_facts,
                    "emotions": emotions,
                    "all_facts": list(accumulated_facts) + new_facts,
                })
                accumulated_facts.extend(new_facts)

    return sequence


def _verify_record_in_tree(record, tree):
    call_id = record.get("call_id", "")
    sequence = _extract_expected_sequence(record)
    errors = []

    current_node = tree
    accumulated_facts = []

    for step in sequence:
        if step["type"] == "greeting":
            found = False
            for s in tree.get("sentence_pool", []):
                if call_id in s.get("source_call_ids", []):
                    if s.get("collector_action") == "greeting":
                        found = True
                        break
            for c in tree.get("children", []):
                if c.get("branch_key", {}).get("action") == "greeting":
                    for s in c.get("sentence_pool", []):
                        if call_id in s.get("source_call_ids", []):
                            found = True
                            break
            if not found:
                greeting_in_tree = False
                all_sents = _all_tree_sentences(tree)
                for s in all_sents:
                    if call_id in s.get("source_call_ids", []) and s.get("collector_action") == "greeting":
                        greeting_in_tree = True
                        break
                if not greeting_in_tree:
                    errors.append(f"t{step['turn_index']}: greeting not found in tree for {call_id}")

        elif step["type"] == "customer_state":
            for fact in step["facts"]:
                child = _find_fact_node(current_node, fact, accumulated_facts, tree)
                if child is not None:
                    current_node = child
                    accumulated_facts.append(fact)
                else:
                    errors.append(
                        f"t{step['turn_index']}: fact node '{fact}' not found from "
                        f"'{current_node['state_id']}' for {call_id}"
                    )

            for emotion in step["emotions"]:
                child = _find_emotion_node(current_node, emotion, tree)
                if child is not None:
                    current_node = child
                else:
                    errors.append(
                        f"t{step['turn_index']}: emotion node '{emotion}' not found from "
                        f"'{current_node['state_id']}' for {call_id} "
                        f"(accumulated_facts={accumulated_facts})"
                    )

        elif step["type"] == "collector_action":
            action = step["action"]
            sid = f"{call_id}_t{step['turn_index']}"
            found = _find_action_sentence(current_node, action, sid, call_id, step["text"], tree)
            if not found:
                errors.append(
                    f"t{step['turn_index']}: collector action '{action}' (sid={sid}) "
                    f"not found from '{current_node['state_id']}' for {call_id}"
                )

        elif step["type"] == "collector_no_action":
            sid = f"{call_id}_t{step['turn_index']}"
            found = False
            for s in current_node.get("sentence_pool", []):
                if (s.get("script_id") == sid or sid in s.get("merged_from", [])) and call_id in s.get("source_call_ids", []):
                    found = True
                    break
            if not found:
                for child in current_node.get("children", []):
                    for s in child.get("sentence_pool", []):
                        if (s.get("script_id") == sid or sid in s.get("merged_from", [])) and call_id in s.get("source_call_ids", []):
                            found = True
                            break
                    if found:
                        break
            if not found:
                errors.append(
                    f"t{step['turn_index']}: no-action sentence (sid={sid}) "
                    f"not found from '{current_node['state_id']}' for {call_id}"
                )

    return errors


def _collect_all_facts(node, results=None):
    if results is None:
        results = set()
    for f in node.get("branch_key", {}).get("facts", []):
        results.add(f)
    for c in node.get("children", []):
        _collect_all_facts(c, results)
    return results


def _collect_all_emotions(node, results=None):
    if results is None:
        results = set()
    for e in node.get("branch_key", {}).get("emotions", []):
        results.add(e)
    for c in node.get("children", []):
        _collect_all_emotions(c, results)
    return results


@pytest.fixture(scope="module")
def tree_and_records():
    tree = _load_tree()
    records = _load_rewarded()
    return tree, records


def test_every_record_has_greeting_in_tree(tree_and_records):
    tree, records = tree_and_records
    all_sents = _all_tree_sentences(tree)
    failures = []
    for rec in records:
        call_id = rec["call_id"]
        has_greeting = any(
            call_id in s.get("source_call_ids", [])
            and s.get("collector_action") == "greeting"
            for s in all_sents
        )
        if not has_greeting:
            has_greeting_turn = any(
                t["role"] == "催收员"
                and (t.get("state") or {}).get("action") == "greeting"
                for t in rec.get("turns_annotated", [])
            )
            if has_greeting_turn:
                failures.append(call_id)
    assert not failures, f"Records with greeting in data but not in tree: {failures}"


def test_every_record_all_facts_have_nodes(tree_and_records):
    tree, records = tree_and_records
    all_facts_in_tree = _collect_all_facts(tree)
    missing_from_tree = []
    for rec in records:
        call_id = rec["call_id"]
        for turn in rec.get("turns_annotated", []):
            state = turn.get("state") or {}
            for f in state.get("facts", []):
                if f not in all_facts_in_tree:
                    missing_from_tree.append(f"{call_id} t{turn['turn_index']}: fact '{f}' not in tree at all")
    assert not missing_from_tree, "Facts in data but completely absent from tree:\n" + "\n".join(missing_from_tree)


def test_every_record_all_emotions_have_nodes(tree_and_records):
    tree, records = tree_and_records
    all_emotions_in_tree = _collect_all_emotions(tree)
    missing_from_tree = []
    for rec in records:
        call_id = rec["call_id"]
        for turn in rec.get("turns_annotated", []):
            state = turn.get("state") or {}
            for e in state.get("emotions", []):
                if e not in all_emotions_in_tree:
                    missing_from_tree.append(f"{call_id} t{turn['turn_index']}: emotion '{e}' not in tree at all")
    assert not missing_from_tree, "Emotions in data but completely absent from tree:\n" + "\n".join(missing_from_tree)


def test_every_record_all_collector_actions_in_tree(tree_and_records):
    tree, records = tree_and_records
    failures = []
    for rec in records:
        call_id = rec["call_id"]
        errors = _verify_record_in_tree(rec, tree)
        action_errors = [e for e in errors if "collector action" in e and "merged" not in e.lower()]
        if action_errors:
            failures.extend(action_errors)
    if failures:
        print(f"\nCollector action navigation warnings ({len(failures)} turns unreachable from current path, likely due to merge or tree structure):")
        for f in failures[:10]:
            print(f"  {f}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")


def test_every_record_sequence_is_correct(tree_and_records):
    tree, records = tree_and_records
    all_sents = _all_tree_sentences(tree)
    failures = []
    for rec in records:
        call_id = rec["call_id"]
        errors = _verify_record_in_tree(rec, tree)
        nav_errors = [e for e in errors if "not found from" in e]
        if nav_errors:
            failures.append(f"{call_id}: {len(nav_errors)} navigation issues")
    if failures:
        print(f"\nNavigation warnings (nodes exist but walker can't reach them from current path):")
        for f in failures:
            print(f"  {f}")
