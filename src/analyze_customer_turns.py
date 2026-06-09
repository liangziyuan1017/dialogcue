import json
from collections import defaultdict
from src.llm_client import call_deepseek_json

SUGGESTED_FACTS = [
    {"group_name": "legal_threat", "keywords": ["被起诉", "法院", "律师函"], "example_turn": ""},
    {"group_name": "debt_evasion", "keywords": ["不认账", "不是我办的", "逃废债"], "example_turn": ""},
    {"group_name": "negotiation_history", "keywords": ["之前协商过", "上次说好的"], "example_turn": ""},
    {"group_name": "card_frozen", "keywords": ["卡冻结了", "不能用卡"], "example_turn": ""},
    {"group_name": "family_issue", "keywords": ["家里出事", "家人生病"], "example_turn": ""},
]

SUGGESTED_EMOTIONS = [
    {"group_name": "anger", "keywords": ["愤怒", "生气", "凭什么"], "example_turn": ""},
    {"group_name": "resignation", "keywords": ["随便吧", "无所谓", "随你们"], "example_turn": ""},
    {"group_name": "embarrassment", "keywords": ["不好意思", "丢人", "难为情"], "example_turn": ""},
]


def _build_customer_prompt(turn_text: str, context_turns: list) -> str:
    ctx = "\n".join(f"  {t['role']}: {t['text']}" for t in context_turns)
    return f"""你是一个催收对话分析专家。分析以下客户发言，提取事实、情绪和还款意愿信号。

上下文:
{ctx}

客户发言: {turn_text}

请以JSON格式输出:
{{
  "facts": [{{"keyword": "关键词", "group": "语义组名(英文snake_case)"}}],
  "emotions": [{{"keyword": "关键词", "group": "语义组名(英文snake_case)"}}],
  "willingness_signal": "resistant|weak|conditional|negotiating|strong"
}}

注意:
- 同一意思的不同说法归入同一group（如"没钱"和"经济困难"都归入financial_hardship）
- group名用英文snake_case
- 如果该发言无明显事实/情绪，对应数组可为空
- willingness_signal必填"""


def _group_results(raw_results: list, dimension: str) -> list:
    groups = defaultdict(lambda: {"keywords": [], "frequency": 0, "example_turn": "", "source": "observed"})
    for result in raw_results:
        for item in result.get(dimension, []):
            group_name = item.get("group", item.get("keyword", "unknown"))
            keyword = item.get("keyword", "")
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


def analyze_customer_turns(records: list) -> dict:
    raw_results = []
    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] != "客户":
                continue
            context_start = max(0, i - 3)
            context_turns = dialog[context_start:i]
            prompt = _build_customer_prompt(turn["text"], context_turns)
            try:
                result = call_deepseek_json(prompt)
                result["_turn_text"] = turn["text"]
                raw_results.append(result)
            except Exception:
                pass

    facts = _group_results(raw_results, "facts")
    emotions = _group_results(raw_results, "emotions")
    facts = _add_suggested(facts, SUGGESTED_FACTS)
    emotions = _add_suggested(emotions, SUGGESTED_EMOTIONS)

    return {"facts": facts, "emotions": emotions}
