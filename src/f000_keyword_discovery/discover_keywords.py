import copy
import json
import os

from f000_keyword_discovery.keyword_prompts import (
    BATCH_SIZE,
    SUGGESTED_ACTIONS,
    SUGGESTED_EMOTIONS,
    SUGGESTED_FACTS,
    _add_suggested,
    _build_cluster_prompt,
    _build_collector_batch_prompt,
    _build_customer_batch_prompt,
    _group_actions,
    _group_items,
)
from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import call_deepseek_json


def discover_keywords(records, output_path: str = None, labeled_output_path: str = None) -> dict:
    labeled_records = copy.deepcopy(records)

    customer_turns = []
    collector_turns = []
    for record in labeled_records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] == "客户":
                context_start = max(0, i - _cfg("context_window.analysis_turns_before", 3))
                context_turns = dialog[context_start:i]
                customer_turns.append((turn, context_turns))
            elif turn["role"] == "催收员":
                collector_turns.append(turn)

    customer_raw = []
    for batch_start in range(0, len(customer_turns), BATCH_SIZE):
        batch = customer_turns[batch_start:batch_start + BATCH_SIZE]
        prompt = _build_customer_batch_prompt([(t["text"], ctx) for t, ctx in batch])
        try:
            results = call_deepseek_json(prompt)
            if isinstance(results, list):
                for j, result in enumerate(results):
                    if batch_start + j >= len(customer_turns):
                        continue
                    turn, _ = customer_turns[batch_start + j]
                    state = {}
                    facts = result.get("facts")
                    if facts:
                        fact_groups = list({f.get("group", f.get("keyword", "")) for f in facts if isinstance(f, dict)})
                        if fact_groups:
                            state["facts"] = fact_groups
                    emotions = result.get("emotions")
                    if emotions:
                        emotion_groups = list({e.get("group", e.get("keyword", "")) for e in emotions if isinstance(e, dict)})
                        if emotion_groups:
                            state["emotions"] = emotion_groups
                    willingness = result.get("willingness") or result.get("willingness_signal")
                    if willingness:
                        state["willingness"] = willingness
                    if state:
                        turn["state"] = state
                    result["_turn_text"] = turn["text"]
                    customer_raw.append(result)
        except Exception:
            pass

    collector_raw = []
    for batch_start in range(0, len(collector_turns), BATCH_SIZE):
        batch = collector_turns[batch_start:batch_start + BATCH_SIZE]
        prompt = _build_collector_batch_prompt([t["text"] for t in batch])
        try:
            results = call_deepseek_json(prompt)
            if isinstance(results, list):
                for j, result in enumerate(results):
                    if batch_start + j >= len(collector_turns):
                        continue
                    turn = collector_turns[batch_start + j]
                    action_group = result.get("action_group")
                    if action_group:
                        turn["state"] = {"action": action_group}
                    result["_turn_text"] = turn["text"]
                    collector_raw.append(result)
        except Exception:
            pass

    facts = _group_items(customer_raw, "facts")
    emotions = _group_items(customer_raw, "emotions")
    facts = _add_suggested(facts, SUGGESTED_FACTS)
    emotions = _add_suggested(emotions, SUGGESTED_EMOTIONS)

    actions = _group_actions(collector_raw)
    actions = _add_suggested(actions, SUGGESTED_ACTIONS)

    willingness_signals = []
    for r in customer_raw:
        sig = r.get("willingness") or r.get("willingness_signal")
        if sig:
            willingness_signals.append(sig)
    unique_signals = list(dict.fromkeys(willingness_signals))

    willingness_levels = []
    if unique_signals:
        cluster_prompt = _build_cluster_prompt(unique_signals)
        try:
            cluster_result = call_deepseek_json(cluster_prompt)
            willingness_levels = cluster_result.get("levels", [])
        except Exception:
            pass

    taxonomy = {
        "facts": facts,
        "emotions": emotions,
        "willingness_levels": willingness_levels,
        "collector_actions": actions,
    }

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "state_keywords.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, ensure_ascii=False, indent=2)

    if labeled_output_path is None:
        labeled_output_path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.py")
    seen_call_ids = set()
    deduped_records = []
    for record in labeled_records:
        call_id = record.get("call_id")
        if call_id in seen_call_ids:
            continue
        seen_call_ids.add(call_id)
        deduped_records.append(record)
    with open(labeled_output_path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(deduped_records, ensure_ascii=False, indent=2))

    return taxonomy
