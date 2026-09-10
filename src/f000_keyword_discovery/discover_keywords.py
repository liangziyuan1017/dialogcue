import json
import os
from pathlib import Path

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
from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl
from f007_infrastructure.llm_client import call_deepseek_json
from f007_infrastructure.logging import get_logger as _get_logger
from f000_keyword_discovery.canonical_relabel import relabel_records

_log = _get_logger(__name__)


def _load_labeled_records():
    path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.jsonl")
    if not os.path.exists(path):
        return []
    return load_jsonl(Path(path))


def _process_customer_batch(batch, customer_raw):
    prompt = _build_customer_batch_prompt([(t["text"], ctx) for t, ctx in batch])
    try:
        results = call_deepseek_json(prompt)
        if isinstance(results, dict) and "results" in results:
            results = results["results"]
        if not isinstance(results, list):
            _log.warning(
                "customer batch: expected list, got %s; skipping %d turns",
                type(results).__name__,
                len(batch),
            )
            return
        for j, result in enumerate(results):
            if j >= len(batch):
                continue
            if not isinstance(result, dict):
                continue
            turn, _ = batch[j]
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
    except Exception as e:
        _log.error("customer batch labeling failed (%d turns): %s", len(batch), e)


def _process_collector_batch(batch, collector_raw):
    prompt = _build_collector_batch_prompt([t["text"] for t in batch])
    try:
        results = call_deepseek_json(prompt)
        if isinstance(results, dict) and "results" in results:
            results = results["results"]
        if not isinstance(results, list):
            _log.warning(
                "collector batch: expected list, got %s; skipping %d turns",
                type(results).__name__,
                len(batch),
            )
            return
        for j, result in enumerate(results):
            if j >= len(batch):
                continue
            if not isinstance(result, dict):
                continue
            turn = batch[j]
            action_group = result.get("action_group")
            if action_group:
                turn["state"] = {"action": action_group}
            result["_turn_text"] = turn["text"]
            collector_raw.append(result)
    except Exception as e:
        _log.error("collector batch labeling failed (%d turns): %s", len(batch), e)


def _label_turns(records):
    customer_raw = []
    collector_raw = []
    customer_batch = []
    collector_batch = []

    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] == "客户":
                context_start = max(0, i - _cfg("context_window.analysis_turns_before", 3))
                context_turns = dialog[context_start:i]
                customer_batch.append((turn, context_turns))
                if len(customer_batch) >= BATCH_SIZE:
                    _process_customer_batch(customer_batch, customer_raw)
                    customer_batch = []
            elif turn["role"] == "催收员":
                collector_batch.append(turn)
                if len(collector_batch) >= BATCH_SIZE:
                    _process_collector_batch(collector_batch, collector_raw)
                    collector_batch = []

    if customer_batch:
        _process_customer_batch(customer_batch, customer_raw)
    if collector_batch:
        _process_collector_batch(collector_batch, collector_raw)

    return customer_raw, collector_raw


def _recompute_taxonomy(all_labeled_records):
    customer_raw = []
    collector_raw = []
    for record in all_labeled_records:
        dialog = record.get("response", {}).get("dialog", [])
        for turn in dialog:
            state = turn.get("state") or {}
            if turn.get("role") == "客户":
                entry = {"_turn_text": turn.get("text", "")}
                facts = state.get("facts", [])
                if facts:
                    entry["facts"] = [{"keyword": f, "group": f} for f in facts]
                emotions = state.get("emotions", [])
                if emotions:
                    entry["emotions"] = [{"keyword": e, "group": e} for e in emotions]
                willingness = state.get("willingness")
                if willingness:
                    entry["willingness"] = willingness
                customer_raw.append(entry)
            elif turn.get("role") == "催收员":
                action = state.get("action")
                if action:
                    collector_raw.append({"action_group": action, "_turn_text": turn.get("text", "")})

    facts = _group_items(customer_raw, "facts")
    emotions = _group_items(customer_raw, "emotions")
    facts = _add_suggested(facts, SUGGESTED_FACTS)
    emotions = _add_suggested(emotions, SUGGESTED_EMOTIONS)
    actions = _group_actions(collector_raw)
    actions = _add_suggested(actions, SUGGESTED_ACTIONS)

    willingness_signals = []
    for r in customer_raw:
        sig = r.get("willingness")
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

    return {
        "facts": facts,
        "emotions": emotions,
        "willingness_levels": willingness_levels,
        "collector_actions": actions,
    }


def label_new_records(new_records, output_path=None, labeled_output_path=None):
    labeled_new = new_records
    _label_turns(labeled_new)
    relabel_stats = relabel_records(labeled_new)
    _log.info(
        "canonical relabel (append): facts %d→%d, emotions %d→%d, turns=%d",
        relabel_stats["facts_in"],
        relabel_stats["facts_out"],
        relabel_stats["emotions_in"],
        relabel_stats["emotions_out"],
        relabel_stats["turns_touched"],
    )

    existing_labeled = _load_labeled_records()
    existing_ids = {r.get("call_id") for r in existing_labeled}
    for record in labeled_new:
        if record.get("call_id") not in existing_ids:
            existing_labeled.append(record)
            existing_ids.add(record.get("call_id"))

    if labeled_output_path is None:
        labeled_output_path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.jsonl")
    write_jsonl(Path(labeled_output_path), existing_labeled)

    taxonomy = _recompute_taxonomy(existing_labeled)
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "state_keywords.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, ensure_ascii=False, indent=2)

    return taxonomy


def discover_keywords(records, output_path: str = None, labeled_output_path: str = None) -> dict:
    labeled_records = records
    _label_turns(labeled_records)
    relabel_stats = relabel_records(labeled_records)
    _log.info(
        "canonical relabel: facts %d→%d, emotions %d→%d, turns=%d",
        relabel_stats["facts_in"],
        relabel_stats["facts_out"],
        relabel_stats["emotions_in"],
        relabel_stats["emotions_out"],
        relabel_stats["turns_touched"],
    )

    # Rebuild taxonomy from canonicalized turn states (not pre-relabel raw groups)
    taxonomy = _recompute_taxonomy(labeled_records)

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "state_keywords.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, ensure_ascii=False, indent=2)

    if labeled_output_path is None:
        labeled_output_path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.jsonl")
    seen_call_ids = set()
    deduped_records = []
    for record in labeled_records:
        call_id = record.get("call_id")
        if call_id in seen_call_ids:
            continue
        seen_call_ids.add(call_id)
        deduped_records.append(record)
    write_jsonl(Path(labeled_output_path), deduped_records)

    return taxonomy
