import json
import os
import re
from pathlib import Path

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl
from f007_infrastructure.llm_client import call_deepseek_json
from f007_infrastructure.logging import get_logger as _get_logger
from f007_infrastructure.retry import retry_call

_log = _get_logger(__name__)


def _load_aligned():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f001_schema_alignment", "data", "output_aligned.jsonl")
    return load_jsonl(Path(data_path))


def _build_explanation_prompt(record, acceptance_type):
    turns = record.get("turns_annotated", [])
    annotated_lines = []
    for t in turns:
        role = "Collector" if t["role"] == "催收员" else "Customer"
        state = t.get("state", {})
        parts = [f"{role}: {t['text']}"]
        if state.get("facts"):
            parts.append(f"  facts: {state['facts']}")
        if state.get("emotions"):
            parts.append(f"  emotions: {state['emotions']}")
        if state.get("willingness"):
            parts.append(f"  willingness: {state['willingness']}")
        if state.get("action"):
            parts.append(f"  action: {state['action']}")
        annotated_lines.append("; ".join(parts))
    dialog_text = "\n".join(annotated_lines)
    prompt = f"""Based on this annotated debt collection call, explain WHY this call succeeded (R=1) in terms of the conversation logic flow.

Focus on: what facts/emotions/willingness the customer showed, and what collector actions led to the successful outcome (customer {acceptance_type}).

Keep the explanation under {_cfg("reward.explanation_max_words", 100)} words. Be specific about the causal chain.

Annotated dialog:
{dialog_text}

Respond in JSON:
{{
  "explanation": "your explanation here"
}}"""
    return prompt


def _build_prompt(record):
    turns = record.get("turns_annotated", [])
    if not isinstance(turns, list):
        turns = []
    window_size = int(_cfg("context_window.reward_last_n_turns", 6))
    last_n = turns[-window_size:] if len(turns) >= window_size else turns
    dialog_lines = []
    for t in last_n:
        role = "Collector" if t["role"] == "催收员" else "Customer"
        dialog_lines.append(f"{role}: {t['text']}")
    dialog_text = "\n".join(dialog_lines)
    prompt = f"""Analyze the last turns of this debt collection call. Determine if the customer made a repayment commitment (R=1) or not (R=0).

R=1 ONLY if the customer explicitly:
- Accepted a repayment plan (调减/MINA/分期), OR
- Promised/agreed to pay a specific amount, OR
- Said they will pay (好的/同意/我会还/我转给你/处理进去)

Mere acknowledgment (我知道了/嗯/了解) without commitment = R=0.

Dialog:
{dialog_text}

Respond in JSON:
{{
  "reward": 0 or 1,
  "customer_acceptance_text": "exact customer text showing acceptance/promise, or null",
  "customer_acceptance_turn_index": turn index of that customer turn, or null,
  "acceptance_type": "accept_plan" or "promise_to_pay" or "agree_to_pay" or null
}}"""
    return prompt


def _find_customer_turn(turns, turn_index):
    if turn_index is not None and 0 <= turn_index < len(turns):
        t = turns[turn_index]
        if t["role"] == "客户":
            return t
    return None


def label_reward(record):
    prompt = _build_prompt(record)
    try:
        llm_result = call_deepseek_json(prompt)
    except Exception:
        return {**record, "reward": 0}

    reward = llm_result.get("reward", 0)
    if reward not in (0, 1):
        reward = 0

    result = {**record, "reward": reward}

    if reward == 1:
        acceptance_text = llm_result.get("customer_acceptance_text")
        acceptance_turn_index = llm_result.get("customer_acceptance_turn_index")
        acceptance_type = llm_result.get("acceptance_type")

        turns = record.get("turns_annotated", [])
        customer_turn = _find_customer_turn(turns, acceptance_turn_index)

        if customer_turn is None and acceptance_text:
            for t in turns:
                if t["role"] == "客户" and acceptance_text in t["text"]:
                    customer_turn = t
                    acceptance_turn_index = t["turn_index"]
                    break

        if customer_turn is None:
            reward = 0
            result["reward"] = 0
            result["reward_action_credit"] = None
            return result

        result["reward_evidence"] = {
            "trigger_text": acceptance_text,
            "trigger_turn_index": acceptance_turn_index,
        }

        result["reward_action_credit"] = {
            "turn_index": acceptance_turn_index,
            "role": "客户",
            "action": acceptance_type or "agree_to_pay",
            "text": customer_turn["text"],
        }

        try:
            expl_prompt = _build_explanation_prompt(record, acceptance_type or "agree_to_pay")
            expl_result = call_deepseek_json(expl_prompt)
            explanation = expl_result.get("explanation", "")
            if len(explanation.split()) > _cfg("reward.explanation_max_words", 100):
                explanation = " ".join(explanation.split()[:_cfg("reward.explanation_max_words", 100)])
        except Exception:
            explanation = ""

        result["reward_action_credit"]["explanation"] = explanation
    else:
        result["reward_action_credit"] = None

    return result


def label_all(records=None):
    if records is None:
        records = _load_aligned()
    results = []
    for i, r in enumerate(records):
        def _process(r=r):
            return label_reward(r)

        def _on_fail(exc, i=i, r=r):
            _log.info(f"  SKIPPED record {i+1}/{len(records)} (call_id={r.get('call_id', '?')}) after 3 retries: {exc}")
            return {**r, "reward": 0, "_retry_failed": True}

        results.append(retry_call(_process, on_fail=_on_fail))
    return results


def cross_validate(rewarded_records):
    warnings = []
    provides_pattern = re.compile(r"(?<!未)提供|运用")
    for rec in rewarded_records:
        if rec["reward"] == 1:
            plan_eval = rec.get("plan_evaluation", "")
            if not provides_pattern.search(plan_eval):
                warnings.append(
                    f"{rec['call_id']}: R=1 but plan_evaluation shows no plan provided — possible mismatch"
                )
    return warnings


def _dedup_by_call_id(records):
    seen = set()
    deduped = []
    dup_count = 0
    for r in records:
        cid = r.get("call_id")
        if cid in seen:
            dup_count += 1
            continue
        seen.add(cid)
        deduped.append(r)
    if dup_count:
        _log.info(f"Dedup: removed {dup_count} duplicate call_id(s), kept {len(deduped)}/{len(records)} records")
    return deduped


def write_output_rewarded(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "output_rewarded.jsonl")
    rewarded = label_all()
    rewarded = _dedup_by_call_id(rewarded)
    write_jsonl(Path(output_path), rewarded)
    return len(rewarded)


if __name__ == "__main__":
    count = write_output_rewarded()
    _log.info(f"Wrote {count} rewarded records to output_rewarded.jsonl")
