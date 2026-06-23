import importlib.util
import json
import os
import re

from infra.llm_client import call_deepseek_json
from infra.retry import retry_call


def _load_aligned():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f001-schema-alignment", "output_aligned.py")
    spec = importlib.util.spec_from_file_location("output_aligned", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


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

Keep the explanation under 100 words. Be specific about the causal chain.

Annotated dialog:
{dialog_text}

Respond in JSON:
{{
  "explanation": "your explanation here"
}}"""
    return prompt


def _build_prompt(record):
    turns = record.get("turns_annotated", [])
    last_n = turns[-6:] if len(turns) >= 6 else turns
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
            if len(explanation.split()) > 100:
                explanation = " ".join(explanation.split()[:100])
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
        def _process():
            return label_reward(r)

        def _on_fail(exc):
            print(f"  SKIPPED record {i+1}/{len(records)} (call_id={r.get('call_id', '?')}) after 3 retries: {exc}")
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


def _python_dumps(obj, indent=2):
    text = json.dumps(obj, indent=indent, ensure_ascii=False)
    text = text.replace(": null", ": None")
    text = text.replace(": true", ": True")
    text = text.replace(": false", ": False")
    return text


def write_output_rewarded(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    rewarded = label_all()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(_python_dumps(rewarded))
    return len(rewarded)


if __name__ == "__main__":
    count = write_output_rewarded()
    print(f"Wrote {count} rewarded records to output_rewarded.py")
