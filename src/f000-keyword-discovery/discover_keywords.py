import copy
import json
import os
from collections import defaultdict
from f000_keyword_discovery.load_data import load_records
from infra.llm_client import call_deepseek_json

BATCH_SIZE = 20

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

SUGGESTED_ACTIONS = [
    {"group_name": "legal_warning", "keywords": ["法务处理", "起诉", "律师函"], "example_turn": ""},
    {"group_name": "asset_investigation", "keywords": ["查资产", "名下房产", "执行"], "example_turn": ""},
    {"group_name": "urgency_pressure", "keywords": ["最后期限", "今天必须", "马上"], "example_turn": ""},
]


def _build_customer_batch_prompt(turns: list) -> str:
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
    "willingness": "resistant|weak|conditional|negotiating|strong" | null
  }}
]

标注规则（严格遵守）:
1. **只标明显的状态**。如果一条发言很难判断事实是什么，或者感觉没有明显情绪，设为null，不要硬编。
2. 短发言（如"嗯"、"好"、"对"、"喂"）几乎总是null/null/null，不要给它们编造标签。
3. facts：只标客户明确陈述的客观事实（失业、生病、工资拖延、多头欠款、卡冻结等）。模糊或推断的事实跳过。
4. emotions：只标明显可感知的情绪（焦虑、愤怒、恳求、防御、疲惫等）。语气平淡或礼貌的跳过。
5. willingness：只标有明确还款态度的发言。如果只是应答/确认/反问，设为null。
6. 同一意思的不同说法归入同一group（如"没钱"和"经济困难"都归入financial_hardship）。
7. group名用英文snake_case。
8. 输出数组长度必须等于{len(turns)}。"""


def _build_collector_batch_prompt(turns: list) -> str:
    turns_text = ""
    for idx, turn_text in enumerate(turns):
        turns_text += f"\n---\n发言{idx+1}: {turn_text}"
    return f"""你是一个催收对话分析专家。分析以下{len(turns)}条连续的催收员发言，只标注**明显的**行为类型。

{turns_text}

请以JSON格式输出一个数组，每条发言对应一个元素:
[
  {{
    "action_group": "语义组名(英文snake_case)" | null
  }}
]

标注规则:
1. **只标明显的催收行为**。短应答（"嗯"、"对"、"好"）、纯确认、单字回复 → 设为null。
2. 常见行为组: greeting(问候), information(告知欠款/方案信息), plan_proposal(提出还款方案), pressure(施压/催促), empathy(共情/理解), legal_threat(法律威胁), closure(收尾/结束通话)
3. 同一意思的不同说法归入同一group。
4. 输出数组长度必须等于{len(turns)}。"""


def _build_cluster_prompt(signals: list) -> str:
    sig_text = "\n".join(f"  - {s}" for s in signals)
    return f"""根据以下从催收对话中提取的还款意愿信号，将它们聚类为有序的意愿等级（从最抗拒到最配合）。

观测到的信号:
{sig_text}

请以JSON格式输出:
{{
  "levels": [
    {{
      "level": "等级名(英文)",
      "definition": "该等级的含义",
      "boundary": "与相邻等级的区别（为什么分在这里而不是上/下一级）",
      "example_turns": [
        {{"text": "原始发言原文", "reason": "为什么归入此等级"}}
      ]
    }}
  ]
}}

要求:
- 等级从最抗拒到最配合排序
- 每个等级至少2个example_turn（从观测数据中选取真实发言）
- boundary要具体说明区分标准
- 等级数量由数据自然聚类决定，不要预设"""


def _group_items(raw_results: list, dimension: str) -> list:
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


def _group_actions(raw_results: list) -> list:
    groups = defaultdict(lambda: {"keywords": [], "frequency": 0, "example_turn": "", "source": "observed"})
    for result in raw_results:
        group_name = result.get("action_group", "unknown")
        keyword = result.get("_turn_text", "")
        g = groups[group_name]
        if keyword and keyword not in g["keywords"]:
            g["keywords"].append(keyword)
        g["frequency"] += 1
        if not g["example_turn"]:
            g["example_turn"] = keyword
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


def discover_keywords(output_path: str = None, labeled_output_path: str = None) -> dict:
    records = load_records()
    labeled_records = copy.deepcopy(records)

    customer_turns = []
    collector_turns = []
    for record in labeled_records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] == "客户":
                context_start = max(0, i - 3)
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
        output_path = os.path.join(os.path.dirname(__file__), "state_keywords.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, ensure_ascii=False, indent=2)

    if labeled_output_path is None:
        labeled_output_path = os.path.join(os.path.dirname(__file__), "..", "f001-schema-alignment", "output_labeled.py")
    with open(labeled_output_path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(labeled_records, ensure_ascii=False, indent=2))

    return taxonomy
