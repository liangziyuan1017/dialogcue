import json
from collections import defaultdict
from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import call_deepseek_json
from f007_infrastructure.retry import retry_call

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

BATCH_SIZE = _cfg("batch_size.analysis", 20)


def _build_batch_prompt(turns: list) -> str:
    turns_text = ""
    for idx, (turn_text, context) in enumerate(turns):
        ctx = "\n".join(f"    {t['role']}: {t['text']}" for t in context)
        turns_text += f"\n---\n发言{idx+1}:\n上下文:\n{ctx}\n客户: {turn_text}"
    return f"""你是一个催收对话分析专家。分析以下{len(turns)}条连续的客户发言，只标注**明显的**事实、情绪和还款意愿。

{turns_text}

请以JSON格式输出一个数组，每条发言对应一个元素:
[
  {{
    "facts": [{{"keyword": "关键词", "group": "语义组名(英文snake_case)"}}] | null,
    "emotions": [{{"keyword": "关键词", "group": "语义组名(英文snake_case)"}}] | null,
    "willingness_signal": "resistant|weak|conditional|negotiating|strong" | null
  }}
]

标注规则（严格遵守）:
1. **只标明显的状态**。如果一条发言很难判断事实是什么，或者感觉没有明显情绪，设为null，不要硬编。
2. 短发言（如"嗯"、"好"、"对"、喂"）几乎总是null/null/null，不要给它们编造标签。
3. facts：只标客户明确陈述的客观事实（失业、生病、工资拖延、多头欠款、卡冻结等）。模糊或推断的事实跳过。
4. emotions：只标明显可感知的情绪（焦虑、愤怒、恳求、防御、疲惫等）。语气平淡或礼貌的跳过。
5. willingness_signal：只标有明确还款态度的发言。如果只是应答/确认/反问，设为null。
6. 同一意思的不同说法归入同一group（如"没钱"和"经济困难"都归入financial_hardship）。
7. group名用英文snake_case。
8. 输出数组长度必须等于{len(turns)}。"""


def _group_results(raw_results: list, dimension: str) -> list:
    groups = defaultdict(lambda: {"keywords": [], "frequency": 0, "example_turn": "", "source": "observed"})
    for result in raw_results:
        for item in (result.get(dimension) or []):
            if isinstance(item, str):
                item = {"keyword": item, "group": item}
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


def _build_customer_prompt(turn_text: str, context_turns: list) -> str:
    return _build_batch_prompt([(turn_text, context_turns)])


def analyze_customer_turns(records: list) -> dict:
    all_turns = []
    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] != "客户":
                continue
            context_start = max(0, i - _cfg("context_window.analysis_turns_before", 3))
            context_turns = dialog[context_start:i]
            all_turns.append((turn["text"], context_turns))

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

                if result is None:
                    continue

                if result.get("facts") is None and result.get("emotions") is None and result.get("willingness_signal") is None:
                    continue
                if batch_start + j < len(all_turns):
                    result["_turn_text"] = all_turns[batch_start + j][0]
                raw_results.append(result)

    facts = _group_results(raw_results, "facts")
    emotions = _group_results(raw_results, "emotions")
    facts = _add_suggested(facts, SUGGESTED_FACTS)
    emotions = _add_suggested(emotions, SUGGESTED_EMOTIONS)

    return {"facts": facts, "emotions": emotions}
