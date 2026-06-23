from collections import defaultdict
from infra.llm_client import call_deepseek_json
from infra.retry import retry_call

SUGGESTED_ACTIONS = [
    {"group_name": "legal_warning", "keywords": ["法务处理", "起诉", "律师函"], "example_turn": ""},
    {"group_name": "asset_investigation", "keywords": ["查资产", "名下房产", "执行"], "example_turn": ""},
    {"group_name": "urgency_pressure", "keywords": ["最后期限", "今天必须", "马上"], "example_turn": ""},
]

BATCH_SIZE = 20


def _build_batch_prompt(turns: list) -> str:
    turns_text = ""
    for idx, turn_text in enumerate(turns):
        turns_text += f"\n---\n发言{idx+1}: {turn_text}"
    return f"""你是一个催收对话分析专家。分析以下{len(turns)}条连续的催收员发言，只标注**明显的**行为类型。

{turns_text}

请以JSON格式输出一个数组，每条发言对应一个元素:
[
  {{
    "action_type": "行为类型关键词" | null,
    "action_group": "语义组名(英文snake_case)" | null,
    "keyword": "行为关键词" | null
  }}
]

标注规则:
1. **只标明显的催收行为**。短应答（"嗯"、"对"、"好"）、纯确认、单字回复 → 全部设为null。
2. 常见行为组: greeting(问候), information(告知欠款/方案信息), plan_proposal(提出还款方案), pressure(施压/催促), empathy(共情/理解), legal_threat(法律威胁), closure(收尾/结束通话)
3. 同一意思的不同说法归入同一group。
4. 输出数组长度必须等于{len(turns)}。"""


def _build_collector_prompt(turn_text: str) -> str:
    return _build_batch_prompt([turn_text])


def _group_collector_results(raw_results: list) -> list:
    groups = defaultdict(lambda: {"keywords": [], "frequency": 0, "example_turn": "", "source": "observed"})
    for result in raw_results:
        group_name = result.get("action_group", result.get("action_type", "unknown"))
        keyword = result.get("keyword", "")
        g = groups[group_name]
        if keyword not in g["keywords"]:
            g["keywords"].append(keyword)
        g["frequency"] += 1
        if not g["example_turn"]:
            g["example_turn"] = result.get("_turn_text", keyword)
    output = []
    for group_name, g in groups.items():
        output.append({
            "group_name": group_name,
            "keywords": g["keywords"],
            "frequency": g["frequency"],
            "example_turn": g["example_turn"],
            "source": g["source"],
        })
    output.sort(key=lambda x: x["frequency"], reverse=True)
    return output


def _add_suggested(groups: list, suggested: list) -> list:
    existing = {g["group_name"] for g in groups}
    for s in suggested:
        if s["group_name"] not in existing:
            groups.append({
                "group_name": s["group_name"],
                "keywords": s["keywords"],
                "frequency": 0,
                "example_turn": s.get("example_turn", ""),
                "source": "suggested",
            })
    return groups


def analyze_collector_turns(records: list) -> dict:
    all_turns = []
    for record in records:
        for turn in record["response"]["dialog"]:
            if turn["role"] != "催收员":
                continue
            all_turns.append(turn["text"])

    raw_results = []
    for batch_start in range(0, len(all_turns), BATCH_SIZE):
        batch = all_turns[batch_start:batch_start + BATCH_SIZE]
        prompt = _build_batch_prompt(batch)
        def _process():
            return call_deepseek_json(prompt)

        def _on_fail(exc):
            print(f"  SKIPPED batch starting at turn {batch_start} after 3 retries: {exc}")
            return None

        batch_result = retry_call(_process, on_fail=_on_fail)
        if batch_result is None:
            continue
        if isinstance(batch_result, list):
            for j, result in enumerate(batch_result):
                if not result or result.get("action_group") is None:
                    continue
                if batch_start + j < len(all_turns):
                    result["_turn_text"] = all_turns[batch_start + j]
                raw_results.append(result)

    actions = _group_collector_results(raw_results)
    actions = _add_suggested(actions, SUGGESTED_ACTIONS)
    return {"collector_actions": actions}
