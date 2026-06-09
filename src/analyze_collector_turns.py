from collections import defaultdict
from src.llm_client import call_deepseek_json

SUGGESTED_ACTIONS = [
    {"group_name": "legal_warning", "keywords": ["法务处理", "起诉", "律师函"], "example_turn": ""},
    {"group_name": "asset_investigation", "keywords": ["查资产", "名下房产", "执行"], "example_turn": ""},
    {"group_name": "urgency_pressure", "keywords": ["最后期限", "今天必须", "马上"], "example_turn": ""},
]


def _build_collector_prompt(turn_text: str) -> str:
    return f"""你是一个催收对话分析专家。分析以下催收员发言，提取其行为类型。

催收员发言: {turn_text}

请以JSON格式输出:
{{
  "action_type": "行为类型关键词",
  "action_group": "语义组名(英文snake_case)",
  "keyword": "行为关键词"
}}

常见行为组: greeting(问候), information(告知信息), plan_proposal(提出方案), pressure(施压), empathy(共情), legal_threat(法律威胁), closure(收尾)
同一意思的不同说法归入同一group。"""


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
    raw_results = []
    for record in records:
        for turn in record["response"]["dialog"]:
            if turn["role"] != "催收员":
                continue
            prompt = _build_collector_prompt(turn["text"])
            try:
                result = call_deepseek_json(prompt)
                result["_turn_text"] = turn["text"]
                raw_results.append(result)
            except Exception:
                pass

    actions = _group_collector_results(raw_results)
    actions = _add_suggested(actions, SUGGESTED_ACTIONS)
    return {"collector_actions": actions}
